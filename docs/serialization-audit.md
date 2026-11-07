# Backend Serialization Audit

## 1. Scope

This audit reviews the FastAPI endpoints in `services/api`, their response schemas, and the protection of sensitive data.

## 2. Endpoint inventory

| Endpoint | Method | Purpose | Current serialization |
|---|---|---|---|
| `/api/health` | GET | API health check | Not serialized |
| `/api/incidents/analyze` | POST | Analyze incident CSV data | Not serialized |
| `/auth/register` | POST | Register a user | Properly serialized: `UserPublic` |
| `/auth/login` | POST | Authenticate a user | Not serialized |
| `/auth/me` | GET | Retrieve current user | Properly serialized: `UserPublic` |
| `/auth/forgot-password` | POST | Request password recovery | Not serialized |
| `/auth/reset-password` | POST | Reset password | Not serialized |
| `/auth/change-password` | POST | Change password | Not serialized |
| `/profiles/me` | GET | Retrieve current profile | Properly serialized: `ProfilePublic` |
| `/profiles/me` | PUT | Create or update current profile | Properly serialized: `ProfilePublic` |
| `/users/me` | GET | Retrieve current user | Properly serialized: `UserPublic` |
| `/users/` | GET | List users | Partially serialized: `UserPublic` |
| `/users/{user_id}` | PUT | Update a user | Properly serialized: `UserPublic` |
| `/users/{user_id}` | DELETE | Delete a user | Not serialized |

## 3. Existing schemas

The following input schemas already exist:

- `UserCreate`
- `ProfileCreate`
- `UserUpdate`
- `ForgotPasswordRequest`
- `ResetPasswordRequest`
- `ChangePasswordRequest`

The following output schemas already exist:

- `UserPublic`
- `ProfilePublic`

## 4. Audit findings

### Properly serialized endpoints

Endpoints using `UserPublic` or `ProfilePublic` already define explicit response models. These schemas limit the fields returned by the API.

### Partially serialized endpoints

`GET /users/` uses `list[UserPublic]`, which filters output fields. However, the route retrieves all database records before serialization. The list response should project only the fields required by the public schema.

### Endpoints without explicit response models

The following endpoints return dictionaries without explicit response schemas:

- `GET /api/health`
- `POST /api/incidents/analyze`
- `POST /auth/login`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /auth/change-password`
- `DELETE /users/{user_id}`

### Security considerations

- User output schemas must never expose `hashed_password`.
- The login response must intentionally include its access token.
- Passwords and reset tokens are input or authentication data, not public user fields.
- Non-admin users must not be allowed to change their own role or active status. The existing users update route contains checks for these fields.

## 5. Implementation plan

1. Add explicit response schemas for health checks and incident analysis.
2. Add a token response schema for login.
3. Add a message response schema for password operations and user deletion.
4. Apply `response_model` to endpoints that currently lack it.
5. Keep input and output schemas separate.
6. Optimize user list responses to return only public fields.
7. Run the available API tests.
8. Verify representative endpoints through FastAPI `/docs`.

## 6. Test status

The directory `services/api/tests` exists but contains no test files.

Automated test execution:
- Command: `python -m pytest services/api/tests -q`
- Result: No tests ran because the directory is empty.

Manual API verification through FastAPI Swagger UI:
- `GET /api/health`: 200 OK.
- `POST /api/incidents/analyze`: 200 OK. Successfully analyzed 100 records.
- `POST /auth/forgot-password`: 200 OK. Returned the expected message response.

The tested responses matched the expected response schemas.

## 7. Final status

- Endpoint inventory completed.
- Serialization audit completed.
- Explicit response schemas implemented.
- Sensitive user fields excluded from public responses.
- User list responses optimized to return public fields only.
- Three API endpoints manually verified through Swagger UI.
- Automated tests remain unavailable because the API test directory is empty.
