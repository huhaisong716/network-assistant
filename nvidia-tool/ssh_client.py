"""SSH 连接管理 - paramiko 封装"""

import os
import paramiko
from typing import Optional, Tuple


class SSHClient:
    def __init__(self, host: str, port: int = 22, user: str = "root", key_path: str = "~/.ssh/id_rsa"):
        self.host = host
        self.port = port
        self.user = user
        self.key_path = os.path.expanduser(key_path)
        self.client: Optional[paramiko.SSHClient] = None

    def connect(self) -> str:
        """建立 SSH 连接，返回空字符串表示成功，否则返回错误信息"""
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # 优先密钥认证
            key = paramiko.RSAKey.from_private_key_file(self.key_path)
            self.client.connect(
                self.host, port=self.port, username=self.user,
                pkey=key, timeout=10, banner_timeout=30
            )
            return ""
        except paramiko.PasswordRequiredException:
            # 密钥需要密码
            return f"SSH 密钥需要密码: {self.key_path}"
        except paramiko.SSHException:
            # 密钥认证失败，尝试密码
            return self._connect_with_password()
        except Exception as e:
            return f"SSH 连接失败: {e}"

    def _connect_with_password(self) -> str:
        """尝试密码认证"""
        import getpass
        password = getpass.getpass(f"{self.user}@{self.host} 密码: ")
        try:
            self.client.connect(
                self.host, port=self.port, username=self.user,
                password=password, timeout=10, banner_timeout=30
            )
            return ""
        except Exception as e:
            return f"密码认证失败: {e}"

    def exec(self, command: str, timeout: int = 60) -> Tuple[str, str, int]:
        """执行远程命令，返回 (stdout, stderr, exit_code)"""
        if not self.client:
            return "", "SSH 未连接", -1
        try:
            _, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            return stdout.read().decode("utf-8", errors="replace"), \
                   stderr.read().decode("utf-8", errors="replace"), exit_code
        except Exception as e:
            return "", str(e), -1

    def exec_sudo(self, command: str, timeout: int = 120) -> Tuple[str, str, int]:
        """执行 sudo 命令"""
        return self.exec(f"sudo -S {command}", timeout=timeout)

    def upload_file(self, local_path: str, remote_path: str) -> str:
        """通过 SFTP 上传文件，返回空字符串表示成功"""
        if not self.client:
            return "SSH 未连接"
        try:
            sftp = self.client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            return ""
        except Exception as e:
            return f"上传失败: {e}"

    def file_exists(self, remote_path: str) -> bool:
        """检查远程文件是否存在"""
        out, _, _ = self.exec(f"test -f {remote_path} && echo 'EXISTS' || echo 'NOT_EXISTS'")
        return "EXISTS" in out

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
