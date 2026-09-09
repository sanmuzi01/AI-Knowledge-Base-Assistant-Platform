"""知识库空间（Knowledge Space）业务层。

分层：FasdtApi/knowledge_space.py -> service/knowledge_space/* -> models/knowledge_space*_dao.py
隔离：一切归属判断走 service.access_control 的 get_owned_space[_async] / user_space_ids[_async]。
"""
