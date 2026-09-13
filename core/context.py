from contextvars import ContextVar

_current_clinic: ContextVar = ContextVar("current_clinic", default=None)
_current_user: ContextVar = ContextVar("current_user", default=None)


def set_current_clinic(clinic):
    _current_clinic.set(clinic)

def get_current_clinic():
    return _current_clinic.get()

def clear_current_clinic():
    _current_clinic.set(None)


def set_current_user(user):
    _current_user.set(user)


def get_current_user():
    return _current_user.get()


def clear_current_user():
    _current_user.set(None)