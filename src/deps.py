
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
 
from src.auth import decode_access_token
from src.database import User, get_db
 
# tokenUrl is just for the interactive /docs UI; it points to our login route
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
 
 
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decodes the bearer token, loads the matching user from the database,
    and raises 401 if the token is missing, invalid, expired, or the
    user no longer exists. Any route that depends on this is protected.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
 
    email = decode_access_token(token)
    if email is None:
        raise credentials_exception
 
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
 
    return user
 
