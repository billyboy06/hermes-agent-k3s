#!/usr/bin/env python3
"""
Minimal ACP client that drives Hermes Agent via JSON-RPC over stdio.
Sends a prompt and streams session_update events until end_turn.
"""
import json
import os
import subprocess
import sys
import threading
from queue import Queue, Empty


class ACPClient:
    def __init__(self, cmd):
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self.next_id = 1
        self.response_q = Queue()
        self.notif_q = Queue()
        self.stderr_q = Queue()
        self._t_out = threading.Thread(target=self._read_stdout, daemon=True)
        self._t_err = threading.Thread(target=self._read_stderr, daemon=True)
        self._t_out.start()
        self._t_err.start()

    def _read_stdout(self):
        for line in self.proc.stdout:
            line = line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                self.stderr_q.put(f"[non-json] {line}")
                continue
            if "id" in msg and ("result" in msg or "error" in msg):
                self.response_q.put(msg)
            else:
                self.notif_q.put(msg)

    def _read_stderr(self):
        for line in self.proc.stderr:
            self.stderr_q.put(line.decode("utf-8", errors="replace").rstrip())

    def request(self, method, params, timeout=300):
        rid = self.next_id
        self.next_id += 1
        msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
        self.proc.stdin.write((json.dumps(msg) + "\n").encode())
        self.proc.stdin.flush()
        # Wait for matching response
        while True:
            try:
                resp = self.response_q.get(timeout=timeout)
            except Empty:
                raise TimeoutError(f"no response for {method}")
            if resp.get("id") == rid:
                return resp

    def drain_notifs(self, label=""):
        out = []
        while True:
            try:
                n = self.notif_q.get_nowait()
                out.append(n)
            except Empty:
                break
        return out

    def drain_stderr(self):
        out = []
        while True:
            try:
                out.append(self.stderr_q.get_nowait())
            except Empty:
                break
        return out

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def main():
    user_prompt = sys.argv[1] if len(sys.argv) > 1 else "/dealradar-triage"
    print(f"[client] launching hermes acp", flush=True)

    client = ACPClient([os.path.expanduser("~/.local/bin/hermes"), "acp", "--accept-hooks"])

    try:
        # 1. Initialize
        init = client.request("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {
                "fs": {"readTextFile": True, "writeTextFile": True},
                "terminal": False,
            },
        })
        print(f"[init] {json.dumps(init.get('result', init.get('error')))[:200]}", flush=True)

        # 2. New session
        ns = client.request("session/new", {
            "cwd": os.path.expanduser("~"),
            "mcpServers": [],
        })
        result = ns.get("result") or {}
        session_id = result.get("sessionId")
        print(f"[session] id={session_id}", flush=True)
        if not session_id:
            print(f"[error] no session id: {json.dumps(ns)[:300]}", flush=True)
            return

        # 3. Send prompt
        print(f"[prompt] sending: {user_prompt}", flush=True)
        prompt_resp_holder = []

        def send_prompt():
            try:
                resp = client.request("session/prompt", {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": user_prompt}],
                }, timeout=900)
                prompt_resp_holder.append(resp)
            except Exception as e:
                prompt_resp_holder.append({"error": str(e)})

        t = threading.Thread(target=send_prompt, daemon=True)
        t.start()

        # Stream notifications
        import time
        start = time.time()
        last_print = start
        while t.is_alive() or not client.notif_q.empty():
            try:
                n = client.notif_q.get(timeout=1.0)
            except Empty:
                if time.time() - last_print > 30:
                    print(f"[client] still waiting... {int(time.time()-start)}s", flush=True)
                    last_print = time.time()
                continue
            method = n.get("method", "?")
            params = n.get("params", {})
            update = params.get("update", {})
            kind = update.get("sessionUpdate") or update.get("type") or "notif"

            if kind == "agent_message_chunk":
                content = update.get("content", {})
                text = content.get("text", "")
                if text:
                    print(text, end="", flush=True)
            elif kind == "tool_call":
                tname = update.get("title") or update.get("name") or "?"
                args = update.get("rawInput") or update.get("input") or {}
                args_str = json.dumps(args)[:150] if args else ""
                print(f"\n[tool] {tname}({args_str})", flush=True)
            elif kind == "tool_call_update":
                content_blocks = update.get("content", [])
                for cb in content_blocks:
                    if cb.get("type") == "content":
                        c = cb.get("content", {})
                        if c.get("type") == "text":
                            text = c.get("text", "")[:200]
                            print(f"  [tool result] {text}", flush=True)
            elif kind == "agent_thought_chunk":
                # Skip thinking — too verbose
                pass
            else:
                print(f"\n[{kind}] {json.dumps(update)[:200]}", flush=True)

        t.join(timeout=5)
        print()
        if prompt_resp_holder:
            r = prompt_resp_holder[0]
            print(f"\n[done] {json.dumps(r.get('result', r))[:300]}", flush=True)
        else:
            print("\n[done] no response captured", flush=True)

        # Drain stderr
        errs = client.drain_stderr()
        if errs:
            print("\n[stderr]")
            for e in errs[-20:]:
                print(f"  {e}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
