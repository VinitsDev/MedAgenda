from functools import wraps

from flask import abort, current_app
from flask_login import current_user


def recepcionista_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.eh_recepcionista:
            abort(403)
        return view(*args, **kwargs)

    return wrapper