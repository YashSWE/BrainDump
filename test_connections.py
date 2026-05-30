import os
import sys
import unittest
import json
from datetime import datetime, timezone
import dotenv

# Load environment variables first
dotenv.load_dotenv()

class TestBrainDumpIntegration(unittest.TestCase):

    def setUp(self):
        self.db_url = os.environ.get("DATABASE_URL")
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        
        # Verify env vars exist
        self.assertIsNotNone(self.db_url, "DATABASE_URL environment variable is missing!")
        self.assertIsNotNone(self.gemini_key, "GEMINI_API_KEY environment variable is missing!")

    def test_1_database_connectivity(self):
        """Test basic connectivity to Supabase PostgreSQL"""
        print("\n--- Testing Supabase Database Connection ---")
        import psycopg2
        try:
            conn = psycopg2.connect(self.db_url)
            self.assertIsNotNone(conn, "Failed to connect to database")
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                res = cur.fetchone()
                self.assertEqual(res[0], 1, "SELECT 1 did not return 1")
            conn.close()
            print("✔ Database connection successful!")
        except Exception as e:
            self.fail(f"Database connection failed: {e}")

    def test_2_database_schema(self):
        """Test that all required tables exist in the schema"""
        print("\n--- Testing Database Schema ---")
        import psycopg2
        expected_tables = {
            "memories", "goals", "events", "financial_facts", "skills",
            "relationships", "delegated_tasks", "followups", "user_profile",
            "memory_embeddings"
        }
        try:
            conn = psycopg2.connect(self.db_url)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public';
                """)
                tables = {row[0] for row in cur.fetchall()}
                
                missing = expected_tables - tables
                self.assertEqual(len(missing), 0, f"Missing tables in database: {missing}")
                print(f"✔ All expected tables exist: {list(expected_tables)}")
                
                # Check vector extension
                cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
                ext = cur.fetchone()
                self.assertIsNotNone(ext, "pgvector extension is NOT installed in Supabase!")
                print("✔ pgvector extension is installed successfully!")
            conn.close()
        except Exception as e:
            self.fail(f"Schema verification failed: {e}")

    def test_3_gemini_embedding_api(self):
        """Test Google Gemini Text Embedding API"""
        print("\n--- Testing Gemini Embedding API ---")
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            result = genai.embed_content(
                model="models/gemini-embedding-2", 
                content="Verification test for BrainDump",
                output_dimensionality=768
            )
            embedding = result.get("embedding")
            self.assertIsNotNone(embedding, "Failed to retrieve embedding from Gemini")
            self.assertEqual(len(embedding), 768, f"Expected 768-dimension embedding, got {len(embedding)}")
            print("✔ Gemini Embedding API returned a valid 768-dimension vector!")
        except Exception as e:
            self.fail(f"Gemini API test failed: {e}")

    def test_4_integrated_crud_and_semantic_search(self):
        """Test insertion, vector embedding generation, pgvector search, and cleanup"""
        print("\n--- Testing Integrated CRUD and Semantic Search ---")
        from models import Memory
        from storage import save_memory, search_memories, delete_memory as db_delete_memory, vec_delete_memory
        
        test_memory = Memory(
            content="Testing continuous deployment validation and integration with Supabase.",
            type="fact",
            category="general",
            tags=["test", "deployment"],
            importance=10,
            source="test-suite"
        )
        
        try:
            # 1. Save memory and embedding
            print("Saving mock memory and generating vector embedding...")
            save_memory(test_memory)
            
            # Save embedding using vec_add_memory equivalent logic in storage
            from storage import vec_add_memory
            vec_add_memory(
                test_memory.id, 
                test_memory.content, 
                {"type": test_memory.type, "category": test_memory.category, "importance": test_memory.importance, "user_id": test_memory.user_id}
            )
            
            # 2. Query/Semantic Search
            print("Searching for the memory semantically...")
            results = search_memories("Supabase continuous deployment validation", n_results=5, user_id=test_memory.user_id)
            
            # Verify we got results and the top result is our test memory
            self.assertTrue(len(results) > 0, "No search results returned")
            found = False
            for r in results:
                if r["id"] == test_memory.id:
                    found = True
                    print(f"✔ Found matching memory semantically (relevance: {r['relevance']})")
                    break
            self.assertTrue(found, "Test memory was not found in semantic search results!")
            
            # 3. Clean up
            print("Cleaning up test memory and embedding...")
            db_delete_memory(test_memory.id)
            vec_delete_memory(test_memory.id)
            
            # Double check it is deleted
            results_post = search_memories("Supabase continuous deployment validation", n_results=5, user_id=test_memory.user_id)
            found_post = any(r["id"] == test_memory.id for r in results_post)
            self.assertFalse(found_post, "Test memory was not properly deleted during cleanup!")
            print("✔ Integration lifecycle (Create -> Embed -> Search -> Delete) successfully verified!")
            
        except Exception as e:
            # Attempt cleanup in case of failure
            try:
                db_delete_memory(test_memory.id)
                vec_delete_memory(test_memory.id)
            except:
                pass
            self.fail(f"Integrated CRUD/Semantic Search failed: {e}")

    def test_5_mcp_tools_registration(self):
        """Test importing the server and verifying tool registration"""
        print("\n--- Testing MCP Tool Registration ---")
        try:
            import asyncio
            from server import mcp
            res = mcp.list_tools()
            if asyncio.iscoroutine(res):
                tools = asyncio.run(res)
            else:
                tools = res
            self.assertTrue(len(tools) > 0, "No MCP tools were registered")
            tool_names = [t.name for t in tools]
            print(f"Registered MCP Tools ({len(tool_names)}): {tool_names}")
            
            # Verify core tools are present
            core_tools = {"store_fact", "add_note", "get_context", "recall", "track_goal", "add_event", "add_financial_fact", "add_skill", "add_relationship", "offload_task", "get_pending_followups"}
            for ct in core_tools:
                self.assertIn(ct, tool_names, f"Core tool '{ct}' is missing from registration!")
            print("✔ All core MCP tools registered successfully!")
        except Exception as e:
            self.fail(f"MCP server import/tool verification failed: {e}")

    def test_6_fastapi_endpoints(self):
        """Test importing ui.py FastAPI routes setup"""
        print("\n--- Testing FastAPI UI & MCP SSE Integration ---")
        try:
            from ui import app
            routes = [r.path for r in app.routes]
            print(f"Registered FastAPI Routes: {routes}")
            
            # Verify SSE mount for MCP and static dashboard endpoint
            self.assertIn("/mcp", routes, "MCP SSE route not registered at /mcp")
            self.assertIn("/", routes, "Root UI index route not registered")
            self.assertIn("/api/memories", routes, "Memories API endpoint not registered")
            self.assertIn("/api/stats", routes, "Stats API endpoint not registered")
            print("✔ FastAPI SSE mount and dashboard API routes are fully configured!")
        except Exception as e:
            self.fail(f"FastAPI app configuration verification failed: {e}")

if __name__ == "__main__":
    unittest.main()
