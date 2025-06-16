from ..models.user import User
from .. import db

def get_all_users():
    return User.query.all()