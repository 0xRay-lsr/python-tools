from flask import Blueprint,jsonify
from ..services import user_service as user

user_dp = Blueprint('user', __name__)

@user_dp.route('/getAll', methods=['GET'])
def get_all_user():
    users = user.get_all_users()
    return jsonify([users.to_dict() for users in users])
