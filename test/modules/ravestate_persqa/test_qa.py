from ravestate_interloc import handle_single_interlocutor_input
import ravestate_nlp
from ravestate_rawio import prop_out as rawio_output, prop_in as rawio_input
from ravestate_interloc import prop_all
import ravestate_persqa
import ravestate_idle
import ravestate_ontology
from ravestate_verbaliser import verbaliser

from ravestate.context import Context
from ravestate.testfixtures import *
from ravestate.receptor import receptor
from ravestate.state import s, Emit
from ravestate.context import sig_startup, sig_shutdown
from ravestate.module import Module
from ravestate.wrappers import ContextWrapper, PropertyWrapper

from reggol import get_logger, set_default_loglevel
logger = get_logger(__name__)


def test_run_qa():
    last_output = ""

    with Module(name="persqa_test"):

        @state(cond=sig_startup, read=prop_all)
        def persqa_hi(ctx: ContextWrapper):
            ravestate_ontology.initialized.wait()
            handle_single_interlocutor_input(ctx, "hi")

        @state(read=rawio_output)
        def raw_out(ctx: ContextWrapper):
            nonlocal last_output
            last_output = ctx[rawio_output]
            logger.info(f"Output: {ctx[rawio_output]}")

    ctx = Context(
        "rawio",
        "ontology",
        "idle",
        "interloc",
        "nlp",
        "persqa",
        "persqa_test"
    )

    @receptor(ctx_wrap=ctx, write=rawio_input)
    def say(ctx: ContextWrapper, what: str):
        ctx[rawio_input] = what

    ctx.emit(sig_startup)
    ctx.run_once()

    assert persqa_hi.wait()

    # Wait for name being asked
    while not raw_out.wait(.1):
        ctx.run_once()
    assert last_output in verbaliser.get_question_list("NAME")

    # Say name
    say("Herbert")

    # Wait for acknowledgement of name
    while not raw_out.wait(.1):
        ctx.run_once()
    assert "herbert" in last_output.lower()

    # Wait for any other question via idle:bored
    while not raw_out.wait(.1):
        ctx.run_once()

    # Roboy now asked some predicate. Let's give some response.
    say("Big Brother")

    # Wait for Roboy's reaction.
    while not raw_out.wait(.1):
        ctx.run_once()


if __name__ == "__main__":
    #from hanging_threads import start_monitoring
    #monitoring_thread = start_monitoring()
    set_default_loglevel("DEBUG")
    test_run_qa()
    exit()
