# Authentication & Authorization Implementation

## Overview
This Django Resolver project now has **Token-based Authentication** with **Role-based Authorization** implemented. This provides secure, stateless authentication perfect for REST APIs and modern frontend applications.

## 🔐 Authentication System

### Token Authentication
- **Type**: DRF Token Authentication (stateless)
- **Tokens**: Auto-generated for each user, persistent until logout
- **Headers**: `Authorization: Token <your_token_here>`

### User Roles & Permissions
1. **User**: Can create tickets, comment on their own tickets, provide feedback
2. **Technician**: Can view/update tickets in their sections + user permissions
3. **Admin/Manager**: Full access to all resources and operations

## 🚀 API Endpoints

### Authentication Endpoints
```bash
POST /api/auth/login/          # Login and get token
POST /api/auth/register/       # Register new user
POST /api/auth/logout/         # Logout and invalidate token
GET  /api/auth/profile/        # Get current user profile
PUT  /api/auth/profile/update/ # Update user profile
```

### Authentication Flow
1. **Register/Login** → Get token
2. **Include token** in all API requests
3. **Logout** → Token invalidated

## 📝 Usage Examples

### 1. Register New User
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "password": "securepassword123",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "user"
  }'
```

**Response:**
```json
{
  "message": "User registered successfully",
  "token": "a1b2c3d4e5f6...",
  "user_id": 5,
  "username": "johndoe",
  "role": "user"
}
```

### 2. Login Existing User
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "password": "securepassword123"
  }'
```

**Response:**
```json
{
  "token": "a1b2c3d4e5f6...",
  "user_id": 5,
  "username": "johndoe",
  "email": "john@example.com",
  "role": "user",
  "first_name": "John",
  "last_name": "Doe",
  "sections": []
}
```

### 3. Access Protected Endpoints
```bash
curl -X GET http://localhost:8000/api/tickets/ \
  -H "Authorization: Token a1b2c3d4e5f6..."
```

### 4. Get User Profile
```bash
curl -X GET http://localhost:8000/api/auth/profile/ \
  -H "Authorization: Token a1b2c3d4e5f6..."
```

### 5. Logout
```bash
curl -X POST http://localhost:8000/api/auth/logout/ \
  -H "Authorization: Token a1b2c3d4e5f6..."
```

## 🛡️ Permission System

### Resource Permissions

| Resource | User | Technician | Admin/Manager |
|----------|------|------------|---------------|
| **Sections** | Read only | Read only | Full access |
| **Facilities** | Read only | Read only | Full access |
| **Tickets** | Own tickets only | Own + Assigned + Section tickets | All tickets |
| **Comments** | Own tickets only | Assigned/Section tickets | All tickets |
| **Feedback** | Own tickets only | Assigned/Section tickets | All tickets |
| **Users** | Own profile only | Own profile only | Full access |
| **Analytics** | ❌ No access | ✅ Can view | ✅ Full access |
| **Reports** | ❌ No access | ✅ Can generate | ✅ Full access |

### Automatic Filtering
- **Users**: Only see their own tickets
- **Technicians**: See tickets they created, assigned to them, or in their sections  
- **Admin/Managers**: See all tickets

## 🔧 Frontend Integration

### React/Vue/Angular Example
```javascript
// Store token after login
localStorage.setItem('authToken', response.data.token);

// Include in API requests
const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Authorization': `Token ${localStorage.getItem('authToken')}`
  }
});

// Example request
const tickets = await apiClient.get('/tickets/');
```

### Authentication Context (React)
```javascript
const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('authToken'));

  const login = async (username, password) => {
    const response = await fetch('/api/auth/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    
    if (response.ok) {
      const data = await response.json();
      setToken(data.token);
      setUser(data);
      localStorage.setItem('authToken', data.token);
    }
  };

  const logout = async () => {
    await fetch('/api/auth/logout/', {
      method: 'POST',
      headers: { 'Authorization': `Token ${token}` }
    });
    setToken(null);
    setUser(null);
    localStorage.removeItem('authToken');
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
```

## ✅ Security Features

1. **Token Invalidation**: Tokens are deleted on logout
2. **Role-based Access**: Automatic permission checking
3. **Object-level Permissions**: Users can only access their own resources
4. **CORS Protection**: Configured for specific frontend origins
5. **Authentication Required**: All endpoints require authentication by default

## 🧪 Testing

Run the authentication test suite:
```bash
# Start Django server
python manage.py runserver

# In another terminal, run tests
python test_authentication.py
```

The test suite validates:
- ✅ User registration
- ✅ Login/logout flow  
- ✅ Token authentication
- ✅ Protected endpoint access
- ✅ Permission enforcement

## 🚀 Deployment Considerations

### Environment Variables
```bash
# .env file
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,api.your-domain.com
ALLOWED_ORIGINS=https://your-frontend.com,https://app.your-domain.com
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

### Security Headers (settings.py)
```python
# Already configured
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '').split(',')

# Consider adding for production
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
```

## 📈 Next Steps

1. **Frontend Integration**: Connect your React/Vue/Angular app
2. **Role Testing**: Create users with different roles to test permissions
3. **API Documentation**: Consider adding Swagger/OpenAPI docs
4. **Rate Limiting**: Implement rate limiting for auth endpoints
5. **Password Reset**: Add password reset functionality
6. **JWT (Optional)**: Consider upgrading to JWT tokens for more features

## 🆘 Troubleshooting

### Common Issues

**401 Unauthorized**
- Check token format: `Authorization: Token <token>`
- Verify token is valid (not logged out)
- Ensure user exists and is active

**403 Forbidden**  
- User lacks required role permissions
- Check role assignments and section memberships

**CORS Errors**
- Update `ALLOWED_ORIGINS` in settings
- Verify frontend URL is included

### Debug Commands
```bash
# Check user tokens
python manage.py shell
>>> from rest_framework.authtoken.models import Token
>>> Token.objects.all()

# Check user roles and sections
>>> from tickets.models import CustomUser
>>> CustomUser.objects.values('username', 'role', 'sections')
```