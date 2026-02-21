# GraphQL Advanced Reference Guide
### FastAPI + Strawberry (Server) · Apollo Client + React (Client)

---

## Table of Contents

1. [Basic Fragments & Named Spreading](#1-basic-fragments--named-spreading)
2. [Inline Fragments, Unions & `__typename`](#2-inline-fragments-unions--__typename)
3. [Fragment Colocation Pattern](#3-fragment-colocation-pattern)
4. [Directives — Built-in & Custom](#4-directives--built-in--custom)
5. [Interfaces](#5-interfaces)
6. [Subscriptions](#6-subscriptions)
7. [Input Types & Mutations](#7-input-types--mutations)
8. [Cursor-Based Pagination](#8-cursor-based-pagination)
9. [Schema Introspection](#9-schema-introspection)
10. [DataLoader — Solving the N+1 Problem](#10-dataloader--solving-the-n1-problem)

---

## 1. Basic Fragments & Named Spreading

> Fragments are reusable field selection sets bound to a specific type. Spread them with `...FragmentName` anywhere that type appears. Fragments can spread other fragments — circular references are caught at parse time.

### 🐍 Server — `schema.py`

```python
import strawberry
from typing import Optional
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

@strawberry.type
class User:
    id: str
    name: str
    email: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: str

@strawberry.type
class Post:
    id: str
    title: str
    body: str
    author: User
    published_at: str

# Mock data
USERS = {
    "1": User(
        id="1", name="Alice", email="alice@dev.io",
        avatar_url="https://i.pravatar.cc/150?img=1",
        bio="Full-stack engineer", created_at="2024-01-01"
    )
}
POSTS = {
    "1": Post(
        id="1", title="GraphQL Mastery",
        body="Fragments are powerful...",
        author=USERS["1"], published_at="2024-06-01"
    )
}

@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: str) -> Optional[User]:
        return USERS.get(id)

    @strawberry.field
    def post(self, id: str) -> Optional[Post]:
        return POSTS.get(id)

schema = strawberry.Schema(query=Query)
app = FastAPI()
app.include_router(GraphQLRouter(schema), prefix="/graphql")
```

### ⚛️ Client — `UserProfile.tsx`

```tsx
import { gql, useQuery } from '@apollo/client';

// Define fragments (colocated with the component)
export const USER_BASIC_FIELDS = gql`
  fragment UserBasicFields on User {
    id
    name
    email
    avatarUrl
  }
`;

// Fragments can spread other fragments
export const USER_FULL_FIELDS = gql`
  fragment UserFullFields on User {
    ...UserBasicFields
    bio
    createdAt
  }
  ${USER_BASIC_FIELDS}
`;

const GET_USER = gql`
  query GetUser($id: String!) {
    user(id: $id) {
      ...UserFullFields
    }
  }
  ${USER_FULL_FIELDS}
`;

export function UserProfile({ userId }: { userId: string }) {
  const { data, loading, error } = useQuery(GET_USER, {
    variables: { id: userId },
  });

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error: {error.message}</p>;

  const { user } = data;
  return (
    <div>
      <img src={user.avatarUrl} alt={user.name} />
      <h2>{user.name}</h2>
      <p>{user.email}</p>
      <p>{user.bio}</p>
      <small>Joined: {user.createdAt}</small>
    </div>
  );
}
```

---

## 2. Inline Fragments, Unions & `__typename`

> **Unions** let a field return completely different types with no shared fields. **Inline fragments** (`... on TypeName`) select fields conditionally based on the resolved concrete type. `__typename` is a free meta-field available on every type.

### 🐍 Server — `union_schema.py`

```python
import strawberry
from typing import Annotated, Union

@strawberry.type
class Article:
    id: str
    title: str
    author: str
    published_at: str

@strawberry.type
class Video:
    id: str
    title: str
    duration_seconds: int
    thumbnail_url: str

@strawberry.type
class UserResult:
    id: str
    name: str
    follower_count: int

# Strawberry union — must be Annotated with a name
SearchResult = Annotated[
    Union[Article, Video, UserResult],
    strawberry.annotated_types.Union(name="SearchResult"),
]

SEARCH_DATA = [
    Article(id="a1", title="Mastering GraphQL",
            author="Alice", published_at="2024-01-01"),
    Video(id="v1", title="GraphQL in 60s",
          duration_seconds=60, thumbnail_url="https://..."),
    UserResult(id="u1", name="Alice", follower_count=1200),
]

@strawberry.type
class Query:
    @strawberry.field
    def search(self, query: str) -> list[SearchResult]:  # type: ignore
        return [
            item for item in SEARCH_DATA
            if query.lower() in (
                getattr(item, 'title', '') +
                getattr(item, 'name', '')
            ).lower()
        ]

schema = strawberry.Schema(query=Query)
```

### ⚛️ Client — `SearchResults.tsx`

```tsx
import { gql, useQuery } from '@apollo/client';

const SEARCH_QUERY = gql`
  query Search($query: String!) {
    search(query: $query) {
      __typename          # always fetch — used to discriminate the type
      ... on Article {
        id
        title
        author
        publishedAt
      }
      ... on Video {
        id
        title
        durationSeconds
        thumbnailUrl
      }
      ... on UserResult {
        id
        name
        followerCount
      }
    }
  }
`;

type SearchItem =
  | { __typename: 'Article';    id: string; title: string; author: string }
  | { __typename: 'Video';      id: string; title: string; durationSeconds: number }
  | { __typename: 'UserResult'; id: string; name: string; followerCount: number };

function SearchResultItem({ item }: { item: SearchItem }) {
  switch (item.__typename) {
    case 'Article':    return <div>📰 {item.title} — by {item.author}</div>;
    case 'Video':      return <div>🎬 {item.title} ({item.durationSeconds}s)</div>;
    case 'UserResult': return <div>👤 {item.name} · {item.followerCount} followers</div>;
    default:           return null;
  }
}

export function SearchResults({ query }: { query: string }) {
  const { data, loading } = useQuery(SEARCH_QUERY, {
    variables: { query },
    skip: !query,
  });

  if (loading) return <p>Searching...</p>;

  return (
    <ul>
      {data?.search.map((item: SearchItem) => (
        <li key={item.id}>
          <SearchResultItem item={item} />
        </li>
      ))}
    </ul>
  );
}
```

---

## 3. Fragment Colocation Pattern

> Each component owns a fragment named `ComponentName_typeName`. The top-level query composes these upward via spreading. When a component's data requirements change, only its fragment changes — the query updates automatically.

### 🐍 Server — `feed_schema.py`

```python
import strawberry
from typing import Optional

@strawberry.type
class Author:
    id: str
    name: str
    avatar_url: str
    role: str

@strawberry.type
class Tag:
    id: str
    name: str
    color: str

@strawberry.type
class Post:
    id: str
    title: str
    excerpt: str
    published_at: str
    author: Author
    tags: list[Tag]
    like_count: int

MOCK_FEED = [
    Post(
        id="1", title="Advanced Fragments",
        excerpt="Colocation is the real power...",
        published_at="2024-06-01",
        author=Author(
            id="u1", name="Alice",
            avatar_url="https://i.pravatar.cc/40?img=1",
            role="Editor"
        ),
        tags=[Tag(id="t1", name="GraphQL", color="#e879f9")],
        like_count=42
    )
]

@strawberry.type
class Query:
    @strawberry.field
    def feed(self) -> list[Post]:
        return MOCK_FEED

schema = strawberry.Schema(query=Query)
```

### ⚛️ Client — `components/Feed.tsx`

```tsx
import { gql, useQuery } from '@apollo/client';

// ── AuthorChip.tsx — owns its own data requirements ──────────────────
export const AUTHOR_CHIP_FRAGMENT = gql`
  fragment AuthorChip_author on Author {
    name
    avatarUrl
    role
  }
`;

export function AuthorChip({ author }: any) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <img src={author.avatarUrl} width={32} style={{ borderRadius: '50%' }} />
      <span>{author.name} · {author.role}</span>
    </div>
  );
}

// ── PostCard.tsx — composes AuthorChip's fragment ────────────────────
export const POST_CARD_FRAGMENT = gql`
  fragment PostCard_post on Post {
    id
    title
    excerpt
    publishedAt
    likeCount
    author { ...AuthorChip_author }
    tags { name color }
  }
  ${AUTHOR_CHIP_FRAGMENT}
`;

export function PostCard({ post }: any) {
  return (
    <article>
      <AuthorChip author={post.author} />
      <h3>{post.title}</h3>
      <p>{post.excerpt}</p>
      {post.tags.map((t: any) => (
        <span key={t.name} style={{ color: t.color }}>#{t.name}</span>
      ))}
      <span>❤️ {post.likeCount}</span>
    </article>
  );
}

// ── Feed.tsx — top-level query composes PostCard's fragment ──────────
const FEED_QUERY = gql`
  query FeedQuery {
    feed { ...PostCard_post }
  }
  ${POST_CARD_FRAGMENT}
`;

export function Feed() {
  const { data, loading } = useQuery(FEED_QUERY);
  if (loading) return <p>Loading feed...</p>;
  return (
    <div>
      {data?.feed.map((p: any) => <PostCard key={p.id} post={p} />)}
    </div>
  );
}
```

---

## 4. Directives — Built-in & Custom

> Built-in directives (`@include`, `@skip`) work on the **client query side**. Custom directives are defined on the **server schema** and add cross-cutting behavior like authorization and caching.

### 🐍 Server — `directives.py`

```python
import strawberry
from strawberry.schema_directive import Location
from strawberry.types import Info
from typing import Optional
import os

# Custom @auth directive on field definitions
@strawberry.schema_directive(
    locations=[Location.FIELD_DEFINITION],
    name="auth"
)
class AuthDirective:
    role: str

# Custom @cacheControl directive
@strawberry.schema_directive(
    locations=[Location.FIELD_DEFINITION, Location.OBJECT],
    name="cacheControl"
)
class CacheControlDirective:
    max_age: int

@strawberry.type
class AdminData:
    secret: str
    user_count: int

@strawberry.type
class PublicPost:
    id: str
    title: str

@strawberry.type
class Query:
    @strawberry.field(directives=[AuthDirective(role="ADMIN")])
    def admin_data(self, info: Info) -> AdminData:
        # Check the authenticated user's role from context
        user = info.context.get("user")
        if not user or user.get("role") != "ADMIN":
            raise Exception("Unauthorized")
        return AdminData(secret="top-secret", user_count=9000)

    @strawberry.field(directives=[CacheControlDirective(max_age=300)])
    def public_posts(self) -> list[PublicPost]:
        return [PublicPost(id="1", title="Hello World")]

schema = strawberry.Schema(
    query=Query,
    schema_directives=[AuthDirective, CacheControlDirective]
)
```

### ⚛️ Client — `ConditionalProfile.tsx`

```tsx
import { gql, useQuery } from '@apollo/client';

// @include and @skip accept a Boolean variable
const GET_PROFILE = gql`
  query GetProfile(
    $id: String!
    $showEmail: Boolean!
    $skipBio: Boolean!
    $withPosts: Boolean!
  ) {
    user(id: $id) {
      id
      name
      email       @include(if: $showEmail)   # only fetched when true
      bio         @skip(if: $skipBio)         # omitted when true
      avatarUrl
      posts @include(if: $withPosts) {
        id
        title
      }
    }
  }
`;

interface Props {
  userId: string;
  isOwner: boolean;  // show email only to the profile owner
  compact: boolean;  // skip bio in compact/card mode
}

export function ConditionalProfile({ userId, isOwner, compact }: Props) {
  const { data, loading } = useQuery(GET_PROFILE, {
    variables: {
      id: userId,
      showEmail: isOwner,
      skipBio: compact,
      withPosts: isOwner,
    },
  });

  if (loading) return <p>Loading...</p>;
  const { user } = data;

  return (
    <div>
      <h2>{user.name}</h2>
      {/* email is absent from the response object entirely when isOwner=false */}
      {user.email && <p>📧 {user.email}</p>}
      {user.bio   && <p>{user.bio}</p>}
      {user.posts && (
        <ul>
          {user.posts.map((p: any) => <li key={p.id}>{p.title}</li>)}
        </ul>
      )}
    </div>
  );
}
```

---

## 5. Interfaces

> Unlike unions (no shared fields), **interfaces** define common fields that all implementing types must provide. Query shared fields without inline fragments; use inline fragments only for type-specific extras.

### 🐍 Server — `interfaces.py`

```python
import strawberry
from typing import Optional

# Interface definitions
@strawberry.interface
class Node:
    id: str

@strawberry.interface
class Timestamped:
    created_at: str
    updated_at: str

# Types implementing multiple interfaces
@strawberry.type
class BlogPost(Node, Timestamped):
    id: str
    created_at: str
    updated_at: str
    title: str
    reading_time_minutes: int

@strawberry.type
class Comment(Node, Timestamped):
    id: str
    created_at: str
    updated_at: str
    body: str
    upvotes: int

@strawberry.type
class MediaFile(Node):
    id: str
    filename: str
    size_bytes: int
    mime_type: str
    # Intentionally does NOT implement Timestamped

@strawberry.type
class Query:
    @strawberry.field
    def node(self, id: str) -> Optional[Node]:
        items: dict[str, Node] = {
            "p1": BlogPost(
                id="p1", title="Hello Interfaces",
                reading_time_minutes=5,
                created_at="2024-01-01", updated_at="2024-01-02"
            ),
            "c1": Comment(
                id="c1", body="Great article!", upvotes=8,
                created_at="2024-01-03", updated_at="2024-01-03"
            ),
            "f1": MediaFile(
                id="f1", filename="diagram.png",
                size_bytes=204800, mime_type="image/png"
            ),
        }
        return items.get(id)

schema = strawberry.Schema(
    query=Query,
    types=[BlogPost, Comment, MediaFile]  # register all implementors
)
```

### ⚛️ Client — `NodeLookup.tsx`

```tsx
import { gql, useQuery } from '@apollo/client';

// Shared fragment works for ANY Node implementor
const NODE_FIELDS = gql`
  fragment NodeFields on Node {
    id           # guaranteed by the interface
    __typename   # discriminate the concrete type
    ... on Timestamped {
      createdAt
      updatedAt
    }
    ... on BlogPost {
      title
      readingTimeMinutes
    }
    ... on Comment {
      body
      upvotes
    }
    ... on MediaFile {
      filename
      sizeBytes
      mimeType
    }
  }
`;

const GET_NODE = gql`
  query GetNode($id: String!) {
    node(id: $id) {
      ...NodeFields
    }
  }
  ${NODE_FIELDS}
`;

export function NodeLookup({ id }: { id: string }) {
  const { data, loading } = useQuery(GET_NODE, { variables: { id } });

  if (loading) return <p>Loading...</p>;
  const node = data?.node;
  if (!node) return <p>Not found</p>;

  return (
    <div>
      <code>[{node.__typename}] id: {node.id}</code>

      {node.__typename === 'BlogPost' && (
        <p>📝 {node.title} · {node.readingTimeMinutes} min read</p>
      )}
      {node.__typename === 'Comment' && (
        <p>💬 {node.body} · ▲ {node.upvotes}</p>
      )}
      {node.__typename === 'MediaFile' && (
        <p>📎 {node.filename} ({node.mimeType})</p>
      )}

      {/* createdAt only present when type also implements Timestamped */}
      {node.createdAt && <small>Created: {node.createdAt}</small>}
    </div>
  );
}
```

---

## 6. Subscriptions

> Real-time updates pushed from server to client over WebSocket. Strawberry uses **async generators** to yield events. Apollo Client needs a split-link setup to route subscriptions over WebSocket and queries/mutations over HTTP.

### 🐍 Server — `subscriptions.py`

```python
import strawberry
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

@strawberry.type
class Message:
    id: str
    body: str
    channel_id: str
    sender_name: str
    sent_at: str

# Simple in-memory pub/sub — replace with Redis in production
_subscribers: dict[str, list[asyncio.Queue]] = {}

async def publish_message(channel_id: str, msg: Message):
    for queue in _subscribers.get(channel_id, []):
        await queue.put(msg)

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def message_received(
        self,
        info: strawberry.types.Info,
        channel_id: str,
    ) -> AsyncGenerator[Message, None]:
        queue: asyncio.Queue = asyncio.Queue()
        _subscribers.setdefault(channel_id, []).append(queue)
        try:
            while True:
                msg = await queue.get()
                yield msg
        finally:
            # Clean up when client disconnects
            _subscribers[channel_id].remove(queue)

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def send_message(
        self, channel_id: str, body: str, sender: str
    ) -> Message:
        import uuid, datetime
        msg = Message(
            id=str(uuid.uuid4()),
            body=body,
            channel_id=channel_id,
            sender_name=sender,
            sent_at=datetime.datetime.utcnow().isoformat()
        )
        await publish_message(channel_id, msg)
        return msg

@strawberry.type
class Query:
    @strawberry.field
    def ping(self) -> str:
        return "pong"

schema = strawberry.Schema(
    query=Query, mutation=Mutation, subscription=Subscription
)
app = FastAPI()
app.include_router(
    GraphQLRouter(schema, subscription_protocols=[
        "graphql-ws",
        "graphql-transport-ws",
    ]),
    prefix="/graphql"
)
```

### ⚛️ Client — `apolloClient.ts` + `Chat.tsx`

```ts
// apolloClient.ts — split-link configuration
import { ApolloClient, InMemoryCache, split, HttpLink } from '@apollo/client';
import { GraphQLWsLink } from '@apollo/client/link/subscriptions';
import { createClient } from 'graphql-ws';
import { getMainDefinition } from '@apollo/client/utilities';

const httpLink = new HttpLink({ uri: 'http://localhost:8000/graphql' });

const wsLink = new GraphQLWsLink(
  createClient({ url: 'ws://localhost:8000/graphql' })
);

// Subscriptions → WebSocket, everything else → HTTP
const splitLink = split(
  ({ query }) => {
    const def = getMainDefinition(query);
    return (
      def.kind === 'OperationDefinition' &&
      def.operation === 'subscription'
    );
  },
  wsLink,
  httpLink,
);

export const client = new ApolloClient({
  link: splitLink,
  cache: new InMemoryCache(),
});
```

```tsx
// Chat.tsx
import { gql, useSubscription, useMutation } from '@apollo/client';
import { useState } from 'react';

const MESSAGE_FRAGMENT = gql`
  fragment MessageFields on Message {
    id
    body
    senderName
    sentAt
    channelId
  }
`;

const MESSAGE_SUBSCRIPTION = gql`
  subscription OnMessage($channelId: String!) {
    messageReceived(channelId: $channelId) {
      ...MessageFields
    }
  }
  ${MESSAGE_FRAGMENT}
`;

const SEND_MESSAGE = gql`
  mutation Send($channelId: String!, $body: String!, $sender: String!) {
    sendMessage(channelId: $channelId, body: $body, sender: $sender) {
      ...MessageFields
    }
  }
  ${MESSAGE_FRAGMENT}
`;

export function Chat({ channelId }: { channelId: string }) {
  const [messages, setMessages] = useState<any[]>([]);
  const [draft, setDraft] = useState('');

  useSubscription(MESSAGE_SUBSCRIPTION, {
    variables: { channelId },
    onData: ({ data }) =>
      setMessages(prev => [...prev, data.data?.messageReceived]),
  });

  const [sendMessage] = useMutation(SEND_MESSAGE);

  return (
    <div>
      <ul>
        {messages.map(m => m && (
          <li key={m.id}>
            <b>{m.senderName}</b>: {m.body}
          </li>
        ))}
      </ul>
      <input value={draft} onChange={e => setDraft(e.target.value)} />
      <button onClick={() => {
        sendMessage({ variables: { channelId, body: draft, sender: 'Me' } });
        setDraft('');
      }}>
        Send
      </button>
    </div>
  );
}
```

---

## 7. Input Types & Mutations

> Using a single **input type** per mutation (rather than many scalar arguments) makes schema evolution non-breaking — you can add optional fields to the input without touching the mutation signature. Return a **payload type** with an `errors` field to handle validation on the client cleanly.

### 🐍 Server — `mutations.py`

```python
import strawberry
from typing import Optional
import uuid

# Input types
@strawberry.input
class CreatePostInput:
    title: str
    body: str
    author_id: str
    tags: list[str] = strawberry.field(default_factory=list)
    published_at: Optional[str] = None

@strawberry.input
class UpdatePostInput:
    title: Optional[str] = None
    body: Optional[str] = None
    tags: Optional[list[str]] = None

@strawberry.input
class DeletePostInput:
    id: str
    reason: Optional[str] = None

# Payload return types — always return errors alongside data
@strawberry.type
class PostPayload:
    post: Optional[Post] = None
    errors: list[str] = strawberry.field(default_factory=list)

@strawberry.type
class DeletePayload:
    deleted_id: Optional[str] = None
    success: bool = False

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_post(self, input: CreatePostInput) -> PostPayload:
        if not input.title.strip():
            return PostPayload(errors=["Title cannot be empty"])

        post = Post(
            id=str(uuid.uuid4()),
            title=input.title,
            body=input.body,
            published_at=input.published_at or "draft",
            author=USERS.get(input.author_id),
            tags=[Tag(id=t, name=t, color="#888") for t in input.tags],
            like_count=0
        )
        POSTS[post.id] = post
        return PostPayload(post=post)

    @strawberry.mutation
    def update_post(self, id: str, input: UpdatePostInput) -> PostPayload:
        post = POSTS.get(id)
        if not post:
            return PostPayload(errors=[f"Post {id} not found"])
        if input.title: post.title = input.title
        if input.body:  post.body  = input.body
        return PostPayload(post=post)

    @strawberry.mutation
    def delete_post(self, input: DeletePostInput) -> DeletePayload:
        if POSTS.pop(input.id, None):
            return DeletePayload(deleted_id=input.id, success=True)
        return DeletePayload(success=False)
```

### ⚛️ Client — `PostEditor.tsx`

```tsx
import { gql, useMutation } from '@apollo/client';
import { useState } from 'react';

// Reusable fragment for the mutation response
const POST_RESULT_FRAGMENT = gql`
  fragment PostResult on PostPayload {
    errors
    post {
      id title body publishedAt
      author { name }
      tags { name }
    }
  }
`;

const CREATE_POST = gql`
  mutation CreatePost($input: CreatePostInput!) {
    createPost(input: $input) {
      ...PostResult
    }
  }
  ${POST_RESULT_FRAGMENT}
`;

const UPDATE_POST = gql`
  mutation UpdatePost($id: String!, $input: UpdatePostInput!) {
    updatePost(id: $id, input: $input) {
      ...PostResult
    }
  }
  ${POST_RESULT_FRAGMENT}
`;

const DELETE_POST = gql`
  mutation DeletePost($input: DeletePostInput!) {
    deletePost(input: $input) {
      deletedId
      success
    }
  }
`;

export function PostEditor({ existingPost }: { existingPost?: any }) {
  const [title, setTitle] = useState(existingPost?.title ?? '');
  const [body, setBody]   = useState(existingPost?.body  ?? '');
  const [errors, setErrors] = useState<string[]>([]);

  const [createPost] = useMutation(CREATE_POST, {
    onCompleted: ({ createPost: res }) => {
      if (res.errors.length) setErrors(res.errors);
      else console.log('Created:', res.post);
    },
    // Append to cached feed list after creation
    update(cache, { data }) {
      // cache.modify({ fields: { feed: ... } })
    },
  });

  const [deletePost] = useMutation(DELETE_POST, {
    variables: { input: { id: existingPost?.id, reason: 'User request' } },
    // Evict the deleted post from Apollo's normalized cache
    update(cache, { data }) {
      const id = data?.deletePost?.deletedId;
      if (id) cache.evict({ id: cache.identify({ __typename: 'Post', id }) });
    },
  });

  const handleSubmit = () => {
    const input = { title, body, authorId: 'u1', tags: ['graphql'] };
    if (existingPost) {
      // useMutation for UPDATE_POST similarly
    } else {
      createPost({ variables: { input } });
    }
  };

  return (
    <div>
      {errors.map(e => <p key={e} style={{ color: 'red' }}>{e}</p>)}
      <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title" />
      <textarea value={body} onChange={e => setBody(e.target.value)} />
      <button onClick={handleSubmit}>
        {existingPost ? 'Update' : 'Create'}
      </button>
      {existingPost && (
        <button onClick={() => deletePost()}>Delete</button>
      )}
    </div>
  );
}
```

---

## 8. Cursor-Based Pagination

> The **Relay Connection Spec** — industry-standard pagination that handles real-time inserts/deletes gracefully. Opaque cursors (base64-encoded IDs) point to stable list positions. The `pageInfo` object tells the client whether more pages exist.

### 🐍 Server — `pagination.py`

```python
import strawberry
from typing import Optional
import base64

def encode_cursor(id: str) -> str:
    return base64.b64encode(f"cursor:{id}".encode()).decode()

def decode_cursor(cursor: str) -> str:
    return base64.b64decode(cursor.encode()).decode().replace("cursor:", "")

@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str] = None
    end_cursor: Optional[str] = None

@strawberry.type
class PostEdge:
    cursor: str
    node: Post

@strawberry.type
class PostConnection:
    edges: list[PostEdge]
    page_info: PageInfo
    total_count: int

# Generate 50 mock posts
ALL_POSTS = [
    Post(
        id=str(i), title=f"Post {i}", body="...",
        published_at="2024-01-01", author=USERS["1"],
        tags=[], like_count=i
    )
    for i in range(1, 51)
]

@strawberry.type
class Query:
    @strawberry.field
    def posts(
        self,
        first: int = 10,
        after: Optional[str] = None,
    ) -> PostConnection:
        posts = ALL_POSTS[:]

        # Apply 'after' cursor for forward pagination
        if after:
            after_id = decode_cursor(after)
            idx = next(
                (i for i, p in enumerate(posts) if p.id == after_id), -1
            )
            posts = posts[idx + 1:]

        sliced = posts[:first]
        edges = [
            PostEdge(cursor=encode_cursor(p.id), node=p)
            for p in sliced
        ]

        return PostConnection(
            edges=edges,
            total_count=len(ALL_POSTS),
            page_info=PageInfo(
                has_next_page=len(posts) > first,
                has_previous_page=after is not None,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
            )
        )
```

### ⚛️ Client — `PaginatedFeed.tsx`

```tsx
import { gql, useQuery } from '@apollo/client';

const POST_EDGE_FRAGMENT = gql`
  fragment PostEdgeFields on PostEdge {
    cursor
    node {
      id title excerpt publishedAt likeCount
      author { name avatarUrl }
    }
  }
`;

const PAGINATED_POSTS = gql`
  query PaginatedPosts($first: Int!, $after: String) {
    posts(first: $first, after: $after) {
      totalCount
      pageInfo {
        hasNextPage
        hasPreviousPage
        endCursor
      }
      edges {
        ...PostEdgeFields
      }
    }
  }
  ${POST_EDGE_FRAGMENT}
`;

const PAGE_SIZE = 10;

export function PaginatedFeed() {
  const { data, loading, fetchMore } = useQuery(PAGINATED_POSTS, {
    variables: { first: PAGE_SIZE },
    notifyOnNetworkStatusChange: true,
  });

  const { edges = [], pageInfo, totalCount } = data?.posts ?? {};

  const loadMore = () => {
    if (!pageInfo?.hasNextPage) return;
    fetchMore({
      variables: { first: PAGE_SIZE, after: pageInfo.endCursor },
      // Merge incoming edges with the existing list
      updateQuery(prev, { fetchMoreResult }) {
        if (!fetchMoreResult) return prev;
        return {
          posts: {
            ...fetchMoreResult.posts,
            edges: [
              ...prev.posts.edges,
              ...fetchMoreResult.posts.edges,
            ],
          },
        };
      },
    });
  };

  return (
    <div>
      <p>{totalCount} total posts</p>
      {edges.map(({ cursor, node }: any) => (
        <article key={cursor}>
          <img src={node.author.avatarUrl} width={24} />
          <h3>{node.title}</h3>
          <p>{node.excerpt}</p>
          <small>❤️ {node.likeCount}</small>
        </article>
      ))}
      {pageInfo?.hasNextPage && (
        <button onClick={loadMore} disabled={loading}>
          {loading ? 'Loading...' : 'Load More'}
        </button>
      )}
    </div>
  );
}
```

> **Tip:** For a cleaner setup, configure `InMemoryCache` `typePolicies` with a `merge` function so `fetchMore` handles merging automatically — no `updateQuery` needed.

```ts
const cache = new InMemoryCache({
  typePolicies: {
    Query: {
      fields: {
        posts: {
          keyArgs: ['first'],
          merge(existing = { edges: [] }, incoming) {
            return { ...incoming, edges: [...existing.edges, ...incoming.edges] };
          },
        },
      },
    },
  },
});
```

---

## 9. Schema Introspection

> GraphQL is self-describing. Disable introspection in production for security. On the client, introspection powers tooling, code generation, and the Apollo cache's type awareness.

### 🐍 Server — `introspection_config.py`

```python
import strawberry
from strawberry.fastapi import GraphQLRouter
from fastapi import FastAPI
from strawberry.printer import print_schema
import os

@strawberry.type
class SchemaVersion:
    version: str
    deployed_at: str
    environment: str

@strawberry.type
class Query:
    @strawberry.field
    def schema_version(self) -> SchemaVersion:
        from datetime import datetime
        return SchemaVersion(
            version="2.1.0",
            deployed_at=datetime.utcnow().isoformat(),
            environment=os.getenv("ENV", "development")
        )

schema = strawberry.Schema(query=Query)

IS_PROD = os.getenv("ENV") == "production"

# Disable GraphiQL playground and introspection in production
graphql_router = GraphQLRouter(
    schema,
    graphiql=not IS_PROD,
    allow_queries_via_get=not IS_PROD,
)

app = FastAPI()
app.include_router(graphql_router, prefix="/graphql")

# Generate full SDL string — pipe this into graphql-codegen
sdl = print_schema(schema)

# Typical codegen.ts config:
# const config: CodegenConfig = {
#   schema: 'http://localhost:8000/graphql',  # or sdl file
#   documents: ['src/**/*.tsx'],
#   generates: {
#     'src/gql/': { preset: 'client' }
#   }
# }
```

### ⚛️ Client — `TypeInspector.tsx`

```tsx
import { gql, useQuery } from '@apollo/client';

// Inspect a specific type's fields at runtime
const INTROSPECT_TYPE = gql`
  query InspectType($typeName: String!) {
    __type(name: $typeName) {
      name
      kind
      description
      fields {
        name
        description
        isDeprecated
        deprecationReason
        type {
          name
          kind
          ofType { name kind }
        }
        args {
          name
          type { name kind }
          defaultValue
        }
      }
    }
  }
`;

// Inspect the entire schema structure
const INTROSPECT_SCHEMA = gql`
  query InspectSchema {
    __schema {
      queryType { name }
      mutationType { name }
      subscriptionType { name }
      types {
        name
        kind
        description
      }
    }
  }
`;

export function TypeInspector({ typeName }: { typeName: string }) {
  const { data, loading } = useQuery(INTROSPECT_TYPE, {
    variables: { typeName },
  });

  if (loading) return <p>Inspecting schema...</p>;
  const type = data?.__type;
  if (!type) return <p>Type not found</p>;

  return (
    <div>
      <h2>{type.name} <small>({type.kind})</small></h2>
      <p>{type.description}</p>
      <table>
        <thead>
          <tr><th>Field</th><th>Type</th><th>Status</th></tr>
        </thead>
        <tbody>
          {type.fields?.map((f: any) => (
            <tr key={f.name}>
              <td>{f.name}</td>
              <td>{f.type.name || f.type.kind}</td>
              <td>{f.isDeprecated ? `⚠️ ${f.deprecationReason}` : '✓'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Practical usage — run graphql-codegen to generate typed hooks:
// npx graphql-codegen --config codegen.ts
//
// Output for every fragment and query:
//   useGetUserQuery()         → typed return shape
//   GetUserQueryVariables     → typed variables
//   UserBasicFieldsFragment   → typed fragment shape
```

---

## 10. DataLoader — Solving the N+1 Problem

> Without batching, fetching 100 posts with their authors triggers 101 DB queries (1 for posts + 1 per author). **DataLoader** collects all `load(id)` calls within a single async tick and fires a single batched query. It also deduplicates repeated IDs automatically.

### 🐍 Server — `dataloaders.py`

```python
import strawberry
from strawberry.dataloader import DataLoader
from strawberry.fastapi import GraphQLRouter, BaseContext
from fastapi import FastAPI
from typing import Optional
import asyncio

# Simulated async DB batch fetch
async def db_get_users_by_ids(ids: list[str]) -> list[Optional[dict]]:
    print(f"🔥 DB HIT — batch loading {len(ids)} users: {ids}")
    await asyncio.sleep(0.01)  # simulate I/O latency
    USER_DB = {
        "u1": {"id": "u1", "name": "Alice", "email": "a@dev.io"},
        "u2": {"id": "u2", "name": "Bob",   "email": "b@dev.io"},
    }
    # Must return a list of the same length and order as ids
    return [USER_DB.get(id) for id in ids]

# DataLoader factory — create a fresh one per request to avoid cross-request caching
def make_user_loader() -> DataLoader:
    async def batch_load_users(ids: list[str]):
        return await db_get_users_by_ids(list(ids))
    return DataLoader(load_fn=batch_load_users)

# Context holds all loaders for the request lifetime
class AppContext(BaseContext):
    user_loader: DataLoader

async def get_context() -> AppContext:
    ctx = AppContext()
    ctx.user_loader = make_user_loader()
    return ctx

# Types
@strawberry.type
class LazyAuthor:
    id: str
    name: str
    email: str

@strawberry.type
class LazyPost:
    id: str
    title: str
    author_id: str

    @strawberry.field
    async def author(self, info: strawberry.types.Info) -> Optional[LazyAuthor]:
        # Called N times, but DataLoader batches into a single DB call
        raw = await info.context.user_loader.load(self.author_id)
        if raw:
            return LazyAuthor(**raw)
        return None

LAZY_POSTS = [
    LazyPost(id="1", title="First",  author_id="u1"),
    LazyPost(id="2", title="Second", author_id="u2"),
    LazyPost(id="3", title="Third",  author_id="u1"),
    # Without DataLoader: 3 separate DB queries (u1, u2, u1)
    # With DataLoader:    1 batched query for ["u1", "u2"] (deduplicated)
]

@strawberry.type
class Query:
    @strawberry.field
    def lazy_posts(self) -> list[LazyPost]:
        return LAZY_POSTS

schema = strawberry.Schema(query=Query)
app = FastAPI()
app.include_router(
    GraphQLRouter(schema, context_getter=get_context),
    prefix="/graphql"
)
```

### ⚛️ Client — `PostList.tsx`

```tsx
import { gql, useQuery } from '@apollo/client';

// The client query is completely unchanged.
// DataLoader is a pure server-side optimization —
// the client just asks for what it needs.
const POSTS_WITH_AUTHORS = gql`
  query PostsWithAuthors {
    lazyPosts {
      id
      title
      author {        # triggers DataLoader.load() per post on the server
        id            # all loads are batched into a single DB call
        name
        email
      }
    }
  }
`;

export function PostList() {
  const { data, loading, error } = useQuery(POSTS_WITH_AUTHORS);

  if (loading) return <p>Loading posts...</p>;
  if (error)   return <p>Error: {error.message}</p>;

  return (
    <div>
      <h2>Posts — watch server logs for a single 🔥 DB HIT</h2>
      {data.lazyPosts.map((post: any) => (
        <div key={post.id}>
          <h3>{post.title}</h3>
          {post.author && (
            <p>✍️ {post.author.name} <small>· {post.author.email}</small></p>
          )}
        </div>
      ))}
    </div>
  );
}
```

> **Apollo cache + DataLoader together:** Apollo's `InMemoryCache` normalizes results by `__typename + id`, so if the same `Author` appears across multiple queries, it's stored once and reused everywhere. Configure `typePolicies` to control merge behavior for paginated or repeated data.

```ts
const cache = new InMemoryCache({
  typePolicies: {
    // Every Author object is stored once, keyed by id
    Author: {
      keyFields: ['id'],
    },
    // Every Post object is stored once, keyed by id
    Post: {
      keyFields: ['id'],
    },
  },
});
```

---

*GraphQL Advanced Reference — FastAPI + Strawberry · Apollo Client + React*
