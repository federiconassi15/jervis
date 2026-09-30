from .models import Permission
ROLE_ORDER={"guest":0,"known":1,"trusted":2,"owner":3}
def allowed(state,user_id,required,authenticated):
    if required is Permission.PUBLIC:return True
    if user_id is None:return False
    user=state.user(user_id)
    if user is None:return False
    level=ROLE_ORDER.get(str(user["role"]),0)
    if required is Permission.KNOWN_USER:return level>=1
    if required is Permission.TRUSTED_USER:return level>=2 or authenticated
    if required is Permission.OWNER:return level>=3 and authenticated
    return authenticated if required is Permission.AUTH_REQUIRED else False
