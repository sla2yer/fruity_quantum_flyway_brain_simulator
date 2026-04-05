from __future__ import annotations

import importlib.util
import io
import signal
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from flywire_wave.agent_tickets import AgentTicket


def _load_run_agent_tickets_module():
    script_path = ROOT / "scripts" / "run_agent_tickets.py"
    spec = importlib.util.spec_from_file_location("run_agent_tickets_script", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RunAgentTicketsScriptTest(unittest.TestCase):
    def test_main_stops_after_current_ticket_when_sigint_is_requested(self) -> None:
        module = _load_run_agent_tickets_module()
        self.addCleanup(sys.modules.pop, "run_agent_tickets_script", None)
        tickets = [
            AgentTicket(ticket_id="FW-001", title="First ticket", metadata={"status": "open"}, sections={}),
            AgentTicket(ticket_id="FW-002", title="Second ticket", metadata={"status": "open"}, sections={}),
        ]
        installed_handlers: dict[int, object] = {}
        run_calls: list[str] = []

        def fake_signal(signum: int, handler: object) -> object:
            previous = installed_handlers.get(signum, signal.SIG_DFL)
            installed_handlers[signum] = handler
            return previous

        def fake_getsignal(signum: int) -> object:
            return installed_handlers.get(signum, signal.SIG_DFL)

        def fake_run_ticket(ticket: AgentTicket, **_: object) -> dict[str, object]:
            run_calls.append(ticket.ticket_id)
            if ticket.ticket_id == "FW-001":
                handler = installed_handlers[signal.SIGINT]
                handler(signal.SIGINT, None)
            return {"ticket_id": ticket.ticket_id, "returncode": 0}

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            summary_path = tmp_dir / "summary.json"
            stdout = io.StringIO()

            with mock.patch.object(module, "parse_ticket_markdown", return_value=tickets):
                with mock.patch.object(module, "filter_tickets", return_value=tickets):
                    with mock.patch.object(module, "select_cli_runner", return_value="/tmp/fake-runner"):
                        with mock.patch.object(module, "run_ticket", side_effect=fake_run_ticket):
                            with mock.patch.object(module, "write_run_summary", return_value=summary_path):
                                with mock.patch.object(module.signal, "signal", side_effect=fake_signal):
                                    with mock.patch.object(module.signal, "getsignal", side_effect=fake_getsignal):
                                        with redirect_stdout(stdout):
                                            exit_code = module.main(["--output-dir", str(tmp_dir / "runs")])

        self.assertEqual(exit_code, 130)
        self.assertEqual(run_calls, ["FW-001"])
        self.assertIn(
            "will stop after the current ticket (FW-001) finishes",
            stdout.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
