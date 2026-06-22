"""paramiko SSH 封装"""
import paramiko
from paramiko.ssh_exception import AuthenticationException, SSHException


class SSHClient:
    def __init__(self, host: str, port: int = 22, user: str = "root",
                 password: str = None, key_path: str = None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.key_path = key_path
        self._client: paramiko.SSHClient | None = None

    def connect(self, timeout: int = 10) -> str:
        """连接服务器，成功返回 ''，失败返回错误信息"""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if self.key_path:
                key = paramiko.RSAKey.from_private_key_file(self.key_path)
                self._client.connect(
                    self.host, port=self.port, username=self.user,
                    pkey=key, timeout=timeout, allow_agent=False,
                )
            else:
                self._client.connect(
                    self.host, port=self.port, username=self.user,
                    password=self.password, timeout=timeout, allow_agent=False,
                )
            return ""
        except AuthenticationException:
            return "认证失败，请检查用户名/密码/密钥"
        except SSHException as e:
            return f"SSH 错误: {e}"
        except TimeoutError:
            return "连接超时，请检查网络和主机地址"
        except Exception as e:
            return f"连接失败: {e}"

    def exec(self, command: str, timeout: int = 60) -> tuple[int, str, str]:
        """执行远程命令，返回 (exit_code, stdout, stderr)"""
        if not self._client:
            return -1, "", "未连接"
        try:
            _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            return exit_code, stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")
        except Exception as e:
            return -1, "", str(e)

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def is_connected(self) -> bool:
        return self._client is not None
