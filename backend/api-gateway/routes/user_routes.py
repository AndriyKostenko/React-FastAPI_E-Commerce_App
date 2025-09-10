from os import path
from uuid import UUID
from fastapi import APIRouter, Request, Depends, BackgroundTasks
import json

from apigateway import api_gateway_manager
from shared.shared_instances import logger
from dependencies.auth_dependencies import (get_current_user, 
                                            require_admin, 
                                            require_user_or_admin)
from schemas.schemas import CurrentUserInfo
from events.publisher import events_publisher


user_proxy = APIRouter(tags=["User Service"])

# Public endpoints (no authentication required)
@user_proxy.post("/register", summary="Register a new user")
async def register_user(request: Request):

    user_service_response = await api_gateway_manager.forward_request(
        request=request,
        service_key="user-service",
        path="/register",

    )
    
    # Check if registration was successful
    if user_service_response.status_code != 201:
        return user_service_response
    
    # parsing the response content (new user data + token)
    response_data = json.loads(user_service_response.body)
    
    # publishing the event with token
    await events_publisher.publish_user_registered(
        user_id=response_data["id"],
        email=response_data["email"],
        role=response_data["role"],
        token=response_data["verification_token"]
        )
    
    # Remove token from response !!!
    del response_data["verification_token"]  
    
    return user_service_response


@user_proxy.post("/login", summary="User login")
async def login_user(request: Request):
    # passing form data as body to user service coz it expects form data for OAuth2
    # so we need to forward the form data as is
    user_service_response = await api_gateway_manager.forward_request(
        request=request,
        service_key="user-service",
        path="/login",)
    
    # Check if login was successful
    if user_service_response.status_code != 200:
        return user_service_response
    
    # publish the login event
    response_data = json.loads(user_service_response.body)
    
    await events_publisher.publish_user_login(
        email=response_data["user_email"],
    )
            
    return user_service_response
    
    
@user_proxy.post("/forgot-password", summary="Request password reset")
async def forgot_password(request: Request):
    body_data = await request.json()
    return await api_gateway_manager.forward_request(
        service_key="user-service",
        method=request.method,
        path="/forgot-password",
        body=body_data,
        headers=request.headers
    )


@user_proxy.post("/password-reset/{token}", summary="Reset password with token")
async def reset_password(request: Request, token: str):
    body_data = await request.json()

    user_service_response =  await api_gateway_manager.forward_request(
        service_key="user-service",
        method=request.method,
        path=f"/password-reset/{token}",
        body=body_data,
        headers=request.headers
    )
    

@user_proxy.post("/activate/{token}", summary="Verify email with token")
async def verify_email(request: Request, token: str):
    body_data = await request.body()
    return await api_gateway_manager.forward_request(
        service_key="user-service",
        method=request.method,
        path=f"/activate/{token}",
        body=body_data,
        headers=request.headers
    )
    






# Protected endpoints with dependencies
@user_proxy.get("/me", summary="Get current user data")
async def get_current_user_data(request: Request,
                                current_user: CurrentUserInfo = Depends(get_current_user)):
    logger.info(f"User: {current_user.email} accessing /me endpoint")
    body_data = await request.body()
    return await api_gateway_manager.forward_request(
        service_key="user-service",
        method=request.method,
        path="/me",
        body=body_data,
        headers=request.headers
    )

@user_proxy.get("/users", summary="Get all users")
async def get_all_users(request: Request,
                        current_user: CurrentUserInfo = Depends(require_admin)):
    logger.info(f"Admin: {current_user.email} accessing all users")
    body_data = await request.body()
    return await api_gateway_manager.forward_request(
        service_key="user-service",
        method=request.method,
        path="/users",
        body=body_data,
        headers=request.headers
    )

@user_proxy.get("/users/email/{user_email}", summary="Get user by email")
async def get_user_by_email(request: Request, 
                            user_email: str):
    # Check authorization using the dependency function
    current_user_data = require_user_or_admin(request=request, target_user_email=user_email)
    body_data = await request.body()
    return await api_gateway_manager.forward_request(
        service_key="user-service",
        method=request.method,
        path=f"/users/email/{current_user_data.email}",
        body=body_data,
        headers=request.headers
    )

@user_proxy.get("/users/id/{user_id}", summary="Get user by ID")
async def get_user_by_id(request: Request, 
                         user_id: UUID):
    # Check authorization using the dependency function
    current_user_data = require_user_or_admin(request, target_user_id=user_id)
    body_data = await request.body()
    return await api_gateway_manager.forward_request(
        service_key="user-service",
        method=request.method,
        path=f"/users/id/{current_user_data.id}",
        body=body_data,
        headers=request.headers
    )