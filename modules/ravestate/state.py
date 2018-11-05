# Ravestate State-related definitions

import logging


class State:

    def __init__(self, *, signal, write, read, triggers, action, is_receptor=False):
        assert(callable(action))
        self.name = action.__name__

        # catch the insane case
        if not len(read) and not len(triggers) and not is_receptor:
            logging.warning(
                f"The state `{self.name}` is not reading any properties, nor waiting for any triggers. " +
                "It will never be activated!")

        # convert read/write properties to tuples
        if isinstance(write, str):
            write = (write,)
        if isinstance(read, str):
            read = (read,)

        # listen to default changed-signals if no signals are given.
        # convert triggers to disjunctive normal form.
        if not len(triggers):
            triggers = tuple((f"{rprop_name}:changed",) for rprop_name in read)
        else:
            if isinstance(triggers, str):
                triggers = (triggers,)
            if isinstance(triggers[0], str):
                triggers = (triggers,)

        self.signal = signal
        self.write_props = write
        self.read_props = read
        self.triggers = triggers
        self.action = action
        self.module_name = ""

    def __call__(self, context, args, kwargs):
        return self.action(context, *args, **kwargs)


def state(*, signal: str="", write: tuple=(), read: tuple=(), triggers: tuple=()):
    """
    Decorator to declare a new state, which may emit a certain signal,
    write to a certain set of properties (calling set, push, pop, delete),
    and read from certain properties (calling read).
    """
    def state_decorator(action):
        nonlocal signal, write, read, triggers
        return State(signal=signal, write=write, read=read, triggers=triggers, action=action)
    return state_decorator


if __name__ == '__main__':

    # test basic decorating annotation
    @state(signal="test-signal", read="myprop", write="myprop", triggers=":idle")
    def test_state(context):
        return "Hello world!"
    assert(test_state.signal == "test-signal")
    assert(test_state.read_props == ("myprop",))
    assert(test_state.triggers == ((":idle",),))
    assert(test_state(None) == "Hello world!")

    # test whether default signals are assigned
    @state(read="myprop")
    def test_default_trigger_assignment(context):
        return "Hello universe!"
    assert(test_default_trigger_assignment.triggers == (("myprop:changed",),))

    @state()
    def insane_state():
        logging.error("You will never see this.")

    logging.debug(test_state(None))
