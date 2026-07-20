from pathlib import Path
import codeop

from agent_smith.sandbox.manager import SandboxManager

class REPLInteractive:
    def __init__(
        self,
        config_path: Path | None,
        mcp_config: dict | None = None,
    ) -> None:
        self.buffer = []
        self.sandbox = SandboxManager(config_path, mcp_config)

    def run(self):
        prompt = "sandbox> "
        try:
            while 1:
                line = input(prompt)
                if line == "exit":
                    break
                self.buffer.append(line)
                python_code = "\n".join(self.buffer)
                try:
                    compiled = codeop.compile_command(python_code)
                except (SyntaxError, ValueError, OverflowError) as e:
                    print(f"Invalid code: {e}")
                    self.buffer.clear()
                    continue
                if compiled is None:
                    prompt = "> "
                    continue

                result = self.sandbox.run(python_code)
                print(result)
                self.buffer.clear()
                prompt = "sandbox> "        
        except EOFError:
            pass
        finally:
            self.sandbox.stop()


        

def main() -> None:
    config_path = Path(f"{Path.cwd()}/agent_smith/sandbox/fake_config.json")
    repl = REPLInteractive(None)
    repl.run()