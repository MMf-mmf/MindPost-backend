# Mind Post API Documentation

This document provides comprehensive documentation for the Mind Post API endpoints.

## Authentication

All API endpoints require authentication using JWT (JSON Web Token).

### Obtaining JWT Token

```
POST /api/token/
```

**Request Body:**
```json
{
  "username": "your-email@example.com",
  "password": "your-password"
}
```

**Response:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### Refreshing JWT Token

```
POST /api/token/refresh/
```

**Request Body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### Verifying JWT Token

```
POST /api/token/verify/
```

**Request Body:**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

## API Endpoints

All API requests must include the JWT token in the Authorization header:

```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

## Mind Posts API

### List Mind Posts

Retrieves a paginated list of brain dumps for the authenticated user.

```
GET /api/brain-dumps/
```

**Parameters:**
- `page`: Page number for pagination (default: 1)
- `page_size`: Number of items per page (default: 20)

**Response:**
```json
{
  "count": 42,
  "next": "http://example.com/api/brain-dumps/?page=2",
  "previous": null,
  "results": [
    {
      "uuid": "123e4567-e89b-12d3-a456-426614174000",
      "created_at": "2025-04-07T14:30:45Z",
      "transcription": "This is a sample transcription with #hashtags",
      "edited": false,
      "tags": ["hashtags"]
    },
    // More brain dumps
  ]
}
```

### Retrieve Single Mind Post

```
GET /api/brain-dumps/{uuid}/
```

**Response:**
```json
{
  "uuid": "123e4567-e89b-12d3-a456-426614174000",
  "created_at": "2025-04-07T14:30:45Z",
  "transcription": "This is a sample transcription with #hashtags",
  "edited": false,
  "tags": ["hashtags"]
}
```

### Create New Mind Post

```
POST /api/brain-dumps/
```

**Note:** Must be sent as `multipart/form-data`.

**Request Body:**
- `audio_file`: Audio recording file (required)

**Response:**
```json
{
  "uuid": "123e4567-e89b-12d3-a456-426614174000",
  "created_at": "2025-04-07T14:30:45Z",
  "transcription": "This is a sample transcription with #hashtags",
  "edited": false,
  "tags": ["hashtags"]
}
```

### Update Mind Post

Updates an existing brain dump. Allows updating the transcription and/or explicitly setting the tags.

```
PUT /api/brain-dumps/{uuid}/
PATCH /api/brain-dumps/{uuid}/
```

**Request Body:**

You can provide either `transcription`, `tags`, or both.

```json
{
  "transcription": "Updated transcription with #newtag and maybe #anothertag",
  "tags": ["explicit_tag1", "explicit_tag2"]
}
```

**Fields:**
- `transcription` (string, optional): The updated transcription text. If provided, the `edited` flag will be set to `true`.
- `tags` (array of strings, optional): A list of tags to explicitly set for the brain dump.

**Behavior:**
- If only `transcription` is provided, tags will be automatically extracted from the transcription content (e.g., `#newtag`, `#anothertag`).
- If `tags` is provided (e.g., `["explicit_tag1", "explicit_tag2"]`), the brain dump's tags will be set exactly to this list, overriding any tags found in the transcription.
- If both are provided, the `transcription` is updated, but the tags are set according to the explicitly provided `tags` list.

**Response:**
```json
{
  "uuid": "123e4567-e89b-12d3-a456-426614174000",
  "created_at": "2025-04-07T14:30:45Z",
  "transcription": "Updated transcription with #newtag and maybe #anothertag",
  "edited": true,
  "tags": ["explicit_tag1", "explicit_tag2"] // Reflects the explicitly set tags
}
```

### Delete Mind Post

```
DELETE /api/brain-dumps/{uuid}/
```

**Response:**
- Status: 204 No Content

### Filter Mind Posts by Tag

```
GET /api/brain-dumps/by_tag/?tag=example
```

**Parameters:**
- `tag`: Tag name to filter by (required)

**Response:**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "uuid": "123e4567-e89b-12d3-a456-426614174000",
      "created_at": "2025-04-07T14:30:45Z",
      "transcription": "This is a sample transcription with #example",
      "edited": false,
      "tags": ["example"]
    },
    // More brain dumps with the specified tag
  ]
}
```

## Posts API

### List Posts

```
GET /api/posts/
```

**Parameters:**
- `page`: Page number for pagination (default: 1)
- `page_size`: Number of items per page (default: 20)

**Response:**
```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "uuid": "123e4567-e89b-12d3-a456-426614174001",
      "content": "This is a tweet",
      "created_at": "2025-04-07T15:30:00Z",
      "status": "posted",
      "post_id": "1234567890",
      "post_type": "twitter"
    },
    // More posts
  ]
}
```

### Retrieve Single Post

```
GET /api/posts/{uuid}/
```

**Response:**
```json
{
  "uuid": "123e4567-e89b-12d3-a456-426614174001",
  "content": "This is a tweet",
  "created_at": "2025-04-07T15:30:00Z",
  "status": "posted",
  "post_id": "1234567890",
  "post_type": "twitter"
}
```

### Create New Post

```
POST /api/posts/
```

**Request Body:**
```json
{
  "content": "This is a new tweet",
  "brain_dump_uuids": ["123e4567-e89b-12d3-a456-426614174000", "223e4567-e89b-12d3-a456-426614174000", "323e4567-e89b-12d3-a456-426614174000"],
  "post_type": "twitter",
  "status": "draft" // or "posted"
}
```

**Response:**
```json
{
  "uuid": "123e4567-e89b-12d3-a456-426614174001",
  "content": "This is a new tweet",
  "created_at": "2025-04-07T15:30:00Z",
  "status": "draft",
  "post_id": null,
  "post_type": "twitter"
}
```

### Update Post

```
PUT /api/posts/{uuid}/
PATCH /api/posts/{uuid}/
```

**Request Body:**
```json
{
  "content": "Updated tweet content",
  "status": "posted"
}
```

**Response:**
```json
{
  "uuid": "123e4567-e89b-12d3-a456-426614174001",
  "content": "Updated tweet content",
  "created_at": "2025-04-07T15:30:00Z",
  "status": "posted",
  "post_id": "1234567890",
  "post_type": "twitter"
}
```

### Delete Post

```
DELETE /api/posts/{uuid}/
```

**Response:**
- Status: 204 No Content

### Generate Post Content from Mind Posts

```
POST /api/posts/generate_from_dumps/
```

**Request Body:**
```json
{
  "brain_dump_uuids": ["123e4567-e89b-12d3-a456-426614174000", "223e4567-e89b-12d3-a456-426614174000", "323e4567-e89b-12d3-a456-426614174000"]
}
```

**Response:**
```json
{
  "posts": [
    {
      "content": "Generated tweet content #tag"
    },
    // Potentially more generated post options
  ]
}
```

## Twitter Connection API

### Get Twitter Connection Status

```
GET /api/twitter-connection/status/
```

**Response when connected:**
```json
{
  "twitter_username": "username",
  "twitter_name": "User Name",
  "connected_at": "2025-04-07T12:00:00Z",
  "is_valid": true
}
```

**Response when not connected:**
```json
{
  "connected": false
}
```

## Error Responses

All API endpoints may return the following error responses:

### 400 Bad Request

```json
{
  "error": "Error message describing the problem"
}
```

### 401 Unauthorized

```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden

```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found

```json
{
  "detail": "Not found."
}
```

### 500 Internal Server Error

```json
{
  "error": "Server error processing request"
}
```
