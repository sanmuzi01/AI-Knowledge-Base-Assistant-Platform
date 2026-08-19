import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
load_dotenv()
# 从 .env 读取加密密钥
_ENCRYPTION_KEY  = os.getenv("LLM_ENCRYPTION_KEY")


def _get_fernet() -> Fernet:
    if not _ENCRYPTION_KEY:
        raise RuntimeError("缺少环境变量 LLM_ENCRYPTION_KEY，请先生成并配置 Fernet 密钥")
    return Fernet(_ENCRYPTION_KEY.encode())


def encrypt(plaintext:str)->str:
    """加密明文，返回密文字符串"""
    return _get_fernet().encrypt(plaintext.encode()).decode()
def decrypt(criphertext:str )->str:
    """解密密文，返回明文字符串"""
    return _get_fernet().decrypt(criphertext.encode()).decode()
