import os
import sys
import unittest
import dotenv

dotenv.load_dotenv()


class TestBrainDumpIntegration(unittest.TestCase):

    def setUp(self):
        self.db_url = os.environ.get("DATABASE_URL")
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        self.assertIsNotNone(self.db_url, "DATABASE_URL environment variable is missing!")
        self.assertIsNotNone(self.gemini_key, "GEMINI_API_KEY environment variable is missing!")

    def test_1_database_connectivity(self):
        """Test basic connectivity to Supabase PostgreSQL"""
        print("\n--- Testing Supabase Database Connection ---")
        import psycopg2
        try:
            conn = psycopg2.connect(self.db_url)
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                self.assertEqual(cur.fetchone()[0], 1)
            conn.close()
            print("✔ Database connection successful!")
        except Exception as e:
            self.fail(f"Database connection failed: {e}")

    def test_2_database_schema(self):
        """Test that all required tables exist"""
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
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
                tables = {row[0] for row in cur.fetchall()}
                missing = expected_tables - tables
                self.assertEqual(len(missing), 0, f"Missing tables: {missing}")
                cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
                self.assertIsNotNone(cur.fetchone(), "pgvector extension not installed!")
            conn.close()
            print(f"✔ All tables exist, pgvector installed!")
        except Exception as e:
            self.fail(f"Schema verification failed: {e}")

    def test_3_gemini_embedding_api(self):
        """Test Google Gemini text-embedding-004 via google-genai SDK"""
        print("\n--- Testing Gemini Embedding API ---")
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.gemini_key, http_options=types.HttpOptions(api_version="v1"))
            result = client.models.embed_content(
                model="gemini-embedding-001",
                contents="Verification test for BrainDump",
                config=types.EmbedContentConfig(output_dimensionality=768),
            )
            embedding = result.embeddings[0].values
            self.assertEqual(len(embedding), 768, f"Expected 768 dims, got {len(embedding)}")
            print("✔ Gemini Embedding API returned a valid 768-dimension vector!")
        except Exception as e:
            self.fail(f"Gemini API test failed: {e}")

    def test_4_integrated_crud_and_semantic_search(self):
        """Test insert → embed → search → delete lifecycle"""
        print("\n--- Testing Integrated CRUD and Semantic Search ---")
        from models import Memory
        from storage import save_memory, search_memories, delete_memory as db_delete, vec_delete_memory, vec_add_memory

        test_memory = Memory(
            content="Testing continuous deployment validation and integration with Supabase.",
            type="fact",
            category="general",
            tags=["test", "deployment"],
            importance=10,
            source="test-suite",
        )
        try:
            save_memory(test_memory)
            vec_add_memory(
                test_memory.id, test_memory.content,
                {"type": test_memory.type, "category": test_memory.category,
                 "importance": test_memory.importance, "user_id": test_memory.user_id}
            )

            results = search_memories("Supabase continuous deployment validation", n_results=5, user_id=test_memory.user_id)
            self.assertTrue(len(results) > 0, "No search results returned")
            found = any(r["id"] == test_memory.id for r in results)
            self.assertTrue(found, "Test memory not found in semantic search!")
            print(f"✔ Memory found semantically (top relevance: {results[0]['relevance']})")

            db_delete(test_memory.id)
            vec_delete_memory(test_memory.id)

            results_post = search_memories("Supabase continuous deployment validation", n_results=5, user_id=test_memory.user_id)
            self.assertFalse(any(r["id"] == test_memory.id for r in results_post), "Memory not deleted!")
            print("✔ CRUD + semantic search lifecycle verified!")
        except Exception as e:
            try:
                db_delete(test_memory.id)
                vec_delete_memory(test_memory.id)
            except Exception:
                pass
            self.fail(f"Integrated CRUD/Search failed: {e}")

    def test_5_mcp_tools_registration(self):
        """Test that all MCP tools are registered"""
        print("\n--- Testing MCP Tool Registration ---")
        try:
            import asyncio
            from server import mcp
            res = mcp.list_tools()
            tools = asyncio.run(res) if asyncio.iscoroutine(res) else res
            tool_names = [t.name for t in tools]
            self.assertTrue(len(tool_names) > 0, "No MCP tools registered!")
            core = {"store_fact", "add_note", "get_context", "recall", "track_goal",
                    "add_event", "add_financial_fact", "add_skill", "add_relationship",
                    "offload_task", "get_pending_followups"}
            for ct in core:
                self.assertIn(ct, tool_names, f"Core tool '{ct}' missing!")
            print(f"✔ {len(tool_names)} MCP tools registered: {tool_names}")
        except Exception as e:
            self.fail(f"MCP tool verification failed: {e}")

    def test_6_fastapi_routes(self):
        """Test FastAPI app routes including chat"""
        print("\n--- Testing FastAPI Routes ---")
        try:
            from ui import app
            routes = [r.path for r in app.routes if hasattr(r, "path")]
            self.assertIn("/", routes, "Root route missing")
            self.assertIn("/api/memories", routes, "Memories route missing")
            self.assertIn("/api/stats", routes, "Stats route missing")
            self.assertIn("/api/chat", routes, "Chat route missing")
            print(f"✔ All routes registered. Chat endpoint: /api/chat")
        except Exception as e:
            self.fail(f"FastAPI route verification failed: {e}")

    def test_7_8_chat_endpoint(self):
        """Test chat: graceful error without key, then live call with Gemini"""
        print("\n--- Testing Chat Endpoint ---")
        import asyncio
        from chat import chat_endpoint, ChatRequest, _sessions

        async def run():
            # Part 1: graceful error when no key
            original = os.environ.pop("GEMINI_API_KEY", None)
            try:
                result = await chat_endpoint(ChatRequest(message="hello"))
                assert "GEMINI_API_KEY" in result.reply, f"Expected key error, got: {result.reply}"
                print("✔ Graceful error when API key missing")
            finally:
                if original:
                    os.environ["GEMINI_API_KEY"] = original

            # Part 2: live chat (runs in same event loop — avoids httpx client closure)
            _sessions.clear()
            result = await chat_endpoint(ChatRequest(message="What data do you have about me right now?"))
            assert len(result.reply) > 10, f"Reply too short: {result.reply}"
            assert len(result.session_id) > 0, "No session ID returned"
            print(f"✔ Live chat works. Tools called: {result.tools_called}")
            print(f"  Reply preview: {result.reply[:120]}...")

        try:
            asyncio.run(run())
        except Exception as e:
            self.fail(f"Chat endpoint test failed: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
