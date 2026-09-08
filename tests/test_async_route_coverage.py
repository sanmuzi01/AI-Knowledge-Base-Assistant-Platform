import inspect
import unittest

from FasdtApi import admin, agent, chat, conversation_route, knowledge, llm_config, login, memory


class AsyncRouteCoverageTest(unittest.TestCase):
    def test_high_frequency_routes_are_async(self):
        """高频接口应优先使用 async 路由，降低同步线程池压力。"""
        route_handlers = [
            login.login,
            login.register,
            login.send_register_sms_code,
            login.get_me,
            login.get_dashboard,
            login.get_profile,
            login.update_profile,
            login.change_password,
            llm_config.list_configs,
            llm_config.supported_models,
            llm_config.save_config,
            llm_config.test_config,
            llm_config.delete_config,
            agent.list_agents,
            agent.get_selected,
            agent.get_agent,
            chat.chat,
            knowledge.list_my_documents,
            knowledge.check_crawl_targets,
            knowledge.knowledge_diagnostics,
            knowledge.upload_document,
            knowledge.upload_documents,
            knowledge.crawl_documents,
            knowledge.list_documents,
            knowledge.search_knowledge,
            memory.list_memories,
            memory.create_memory,
            memory.update_memory,
            memory.delete_memory,
            memory.clear_memories,
            conversation_route.create_conversation,
            conversation_route.list_conversations,
            conversation_route.get_conversation,
            conversation_route.get_messages,
            conversation_route.update_conversation,
            conversation_route.update_conversation_flags,
            conversation_route.delete_conversation,
            admin.admin_overview,
            admin.admin_users,
            admin.admin_user_detail,
            admin.admin_update_user_roles,
            admin.admin_update_user_status,
            admin.admin_reset_user_password,
            admin.admin_delete_user,
        ]
        sync_handlers = [handler.__name__ for handler in route_handlers if not inspect.iscoroutinefunction(handler)]
        self.assertEqual([], sync_handlers)


if __name__ == "__main__":
    unittest.main()
