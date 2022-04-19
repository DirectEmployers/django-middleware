def assert_function_registered_as_signal(receiver, sender, signal):
    """
    Verify that a particular function (receiver) is registered to given
    sender (often a Model) under a particular signal (post_save, pre_save, etc)

    This can be used to write tests that ensure a signal is actually being
    fired, thereby freeing up other tests to unit-test the signal's
    business logic

    :param receiver:
        A function or an instance method which is to receive signals.
    :param sender:
        The sender to which the receiver should respond. Must either be
        a Python object, or None to receive events from any sender.
    :param signal:
        Signal class to be tested. This essentially boils down to what type
        of signal is desired (post_save, pre_save, etc)
    :return:
        AssertionError if receiver is not registered to the signal with the
        given sender
    """
    live_receivers = signal._live_receivers(sender)
    assert receiver in live_receivers, "Receiver was not registered with sender"
