# Migrating Vite React JS Project to TypeScript

## Initial Project Structure

```
src/
├── components/
│   ├── Button/
│   │   ├── Button.jsx
│   │   ├── Button.module.css
│   │   └── index.js
│   ├── Card/
│   │   ├── Card.jsx
│   │   ├── Card.module.css
│   │   └── index.js
│   ├── UserProfile/
│   │   ├── UserProfile.jsx          # Complex component
│   │   ├── UserProfile.module.css
│   │   ├── ProfileHeader.jsx        # Child component
│   │   ├── ProfileStats.jsx         # Child component
│   │   └── index.js
│   └── shared/
│       ├── Avatar.jsx
│       └── Badge.jsx
├── hooks/
│   ├── useAuth.js
│   └── useFetch.js
├── utils/
│   ├── formatters.js
│   └── validators.js
├── App.jsx
└── main.jsx
```

## Step 1: Initial TypeScript Setup

### 1.1 Install TypeScript Dependencies

```bash
npm install -D typescript @types/react @types/react-dom
```

### 1.2 Create tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    
    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    
    /* Allow JS during migration */
    "allowJs": true,
    "checkJs": false,
    
    /* Linting */
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

### 1.3 Update vite.config.js

Rename to `vite.config.ts` and update:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
```

## Step 2: Migration Strategy - Bottom-Up Approach

Start with leaf components (no dependencies) and work up to complex components.

### Phase 1: Migrate Simple/Leaf Components

#### Before: Avatar.jsx
```javascript
export default function Avatar({ src, alt, size = 'medium' }) {
  const sizes = {
    small: '32px',
    medium: '48px',
    large: '64px'
  };
  
  return (
    <img 
      src={src} 
      alt={alt} 
      style={{ width: sizes[size], height: sizes[size], borderRadius: '50%' }}
    />
  );
}
```

#### After: Avatar.tsx
```typescript
export type AvatarSize = 'small' | 'medium' | 'large';

export interface AvatarProps {
  src: string;
  alt: string;
  size?: AvatarSize;
}

export default function Avatar({ src, alt, size = 'medium' }: AvatarProps) {
  const sizes: Record<AvatarSize, string> = {
    small: '32px',
    medium: '48px',
    large: '64px'
  };
  
  return (
    <img 
      src={src} 
      alt={alt} 
      style={{ width: sizes[size], height: sizes[size], borderRadius: '50%' }}
    />
  );
}
```

#### Update index.js → index.ts
```typescript
export { default } from './Avatar';
export type { AvatarProps, AvatarSize } from './Avatar';
```

### Phase 2: Migrate Button Component

#### Before: Button.jsx
```javascript
export default function Button({ 
  children, 
  onClick, 
  variant = 'primary', 
  disabled = false,
  size = 'medium'
}) {
  return (
    <button 
      onClick={onClick}
      disabled={disabled}
      className={`btn btn-${variant} btn-${size}`}
    >
      {children}
    </button>
  );
}
```

#### After: Button.tsx
```typescript
import { ReactNode, MouseEvent } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger';
export type ButtonSize = 'small' | 'medium' | 'large';

export interface ButtonProps {
  children: ReactNode;
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  size?: ButtonSize;
  type?: 'button' | 'submit' | 'reset';
}

export default function Button({ 
  children, 
  onClick, 
  variant = 'primary', 
  disabled = false,
  size = 'medium',
  type = 'button'
}: ButtonProps) {
  return (
    <button 
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`btn btn-${variant} btn-${size}`}
    >
      {children}
    </button>
  );
}
```

### Phase 3: Migrate Child Components

#### Before: ProfileStats.jsx
```javascript
export default function ProfileStats({ posts, followers, following }) {
  return (
    <div className="profile-stats">
      <div className="stat">
        <span className="stat-value">{posts}</span>
        <span className="stat-label">Posts</span>
      </div>
      <div className="stat">
        <span className="stat-value">{followers}</span>
        <span className="stat-label">Followers</span>
      </div>
      <div className="stat">
        <span className="stat-value">{following}</span>
        <span className="stat-label">Following</span>
      </div>
    </div>
  );
}
```

#### After: ProfileStats.tsx
```typescript
export interface ProfileStatsProps {
  posts: number;
  followers: number;
  following: number;
}

export default function ProfileStats({ posts, followers, following }: ProfileStatsProps) {
  return (
    <div className="profile-stats">
      <div className="stat">
        <span className="stat-value">{posts.toLocaleString()}</span>
        <span className="stat-label">Posts</span>
      </div>
      <div className="stat">
        <span className="stat-value">{followers.toLocaleString()}</span>
        <span className="stat-label">Followers</span>
      </div>
      <div className="stat">
        <span className="stat-value">{following.toLocaleString()}</span>
        <span className="stat-label">Following</span>
      </div>
    </div>
  );
}
```

### Phase 4: Migrate Complex Component

#### Before: UserProfile.jsx
```javascript
import { useState, useEffect } from 'react';
import Avatar from '../shared/Avatar';
import Button from '../Button';
import Card from '../Card';
import ProfileStats from './ProfileStats';

export default function UserProfile({ userId, onFollow, onMessage }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isFollowing, setIsFollowing] = useState(false);

  useEffect(() => {
    fetchUser(userId);
  }, [userId]);

  const fetchUser = async (id) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/users/${id}`);
      const data = await response.json();
      setUser(data);
      setIsFollowing(data.isFollowing);
    } catch (error) {
      console.error('Failed to fetch user:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFollow = () => {
    setIsFollowing(!isFollowing);
    onFollow?.(userId, !isFollowing);
  };

  if (loading) return <div>Loading...</div>;
  if (!user) return <div>User not found</div>;

  return (
    <Card>
      <div className="user-profile">
        <Avatar src={user.avatar} alt={user.name} size="large" />
        <h2>{user.name}</h2>
        <p className="username">@{user.username}</p>
        <p className="bio">{user.bio}</p>
        
        <ProfileStats 
          posts={user.stats.posts}
          followers={user.stats.followers}
          following={user.stats.following}
        />
        
        <div className="actions">
          <Button onClick={handleFollow} variant={isFollowing ? 'secondary' : 'primary'}>
            {isFollowing ? 'Unfollow' : 'Follow'}
          </Button>
          <Button onClick={() => onMessage?.(userId)} variant="secondary">
            Message
          </Button>
        </div>
      </div>
    </Card>
  );
}
```

#### After: UserProfile.tsx
```typescript
import { useState, useEffect } from 'react';
import Avatar from '../shared/Avatar';
import Button from '../Button';
import Card from '../Card';
import ProfileStats from './ProfileStats';

// Define types for user data
export interface UserStats {
  posts: number;
  followers: number;
  following: number;
}

export interface User {
  id: string;
  name: string;
  username: string;
  avatar: string;
  bio: string;
  stats: UserStats;
  isFollowing: boolean;
}

export interface UserProfileProps {
  userId: string;
  onFollow?: (userId: string, isFollowing: boolean) => void;
  onMessage?: (userId: string) => void;
}

export default function UserProfile({ userId, onFollow, onMessage }: UserProfileProps) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isFollowing, setIsFollowing] = useState<boolean>(false);

  useEffect(() => {
    fetchUser(userId);
  }, [userId]);

  const fetchUser = async (id: string): Promise<void> => {
    setLoading(true);
    try {
      const response = await fetch(`/api/users/${id}`);
      if (!response.ok) {
        throw new Error('Failed to fetch user');
      }
      const data: User = await response.json();
      setUser(data);
      setIsFollowing(data.isFollowing);
    } catch (error) {
      console.error('Failed to fetch user:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFollow = (): void => {
    setIsFollowing(!isFollowing);
    onFollow?.(userId, !isFollowing);
  };

  if (loading) return <div>Loading...</div>;
  if (!user) return <div>User not found</div>;

  return (
    <Card>
      <div className="user-profile">
        <Avatar src={user.avatar} alt={user.name} size="large" />
        <h2>{user.name}</h2>
        <p className="username">@{user.username}</p>
        <p className="bio">{user.bio}</p>
        
        <ProfileStats 
          posts={user.stats.posts}
          followers={user.stats.followers}
          following={user.stats.following}
        />
        
        <div className="actions">
          <Button onClick={handleFollow} variant={isFollowing ? 'secondary' : 'primary'}>
            {isFollowing ? 'Unfollow' : 'Follow'}
          </Button>
          <Button onClick={() => onMessage?.(userId)} variant="secondary">
            Message
          </Button>
        </div>
      </div>
    </Card>
  );
}
```

## Step 3: Migrate Hooks

#### Before: useFetch.js
```javascript
import { useState, useEffect } from 'react';

export function useFetch(url) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(url);
        const json = await response.json();
        setData(json);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [url]);

  return { data, loading, error };
}
```

#### After: useFetch.ts
```typescript
import { useState, useEffect } from 'react';

export interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

export function useFetch<T = unknown>(url: string): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const fetchData = async (): Promise<void> => {
      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const json: T = await response.json();
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Unknown error'));
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [url]);

  return { data, loading, error };
}
```

## Step 4: Migrate Utils

#### Before: validators.js
```javascript
export function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function isValidUsername(username) {
  return /^[a-zA-Z0-9_]{3,20}$/.test(username);
}
```

#### After: validators.ts
```typescript
export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function isValidUsername(username: string): boolean {
  return /^[a-zA-Z0-9_]{3,20}$/.test(username);
}

export function validatePassword(password: string): { 
  isValid: boolean; 
  errors: string[] 
} {
  const errors: string[] = [];
  
  if (password.length < 8) {
    errors.push('Password must be at least 8 characters');
  }
  if (!/[A-Z]/.test(password)) {
    errors.push('Password must contain an uppercase letter');
  }
  if (!/[0-9]/.test(password)) {
    errors.push('Password must contain a number');
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
}
```

## Step 5: Create Shared Types

Create `src/types/index.ts` for shared types:

```typescript
// API Response types
export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: number;
}

export interface ApiError {
  message: string;
  code: string;
  status: number;
}

// Common types
export type ID = string | number;

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

// Re-export component types
export type { User, UserStats } from '../components/UserProfile/UserProfile';
export type { ButtonProps, ButtonVariant } from '../components/Button/Button';
```

## Migration Checklist

- [ ] Install TypeScript dependencies
- [ ] Create tsconfig.json with `allowJs: true`
- [ ] Update vite.config to .ts
- [ ] Migrate simple/leaf components first
- [ ] Migrate child components
- [ ] Migrate complex parent components
- [ ] Migrate hooks
- [ ] Migrate utilities
- [ ] Create shared types file
- [ ] Update main.jsx → main.tsx
- [ ] Update App.jsx → App.tsx
- [ ] Enable strict mode incrementally
- [ ] Remove `allowJs` once migration is complete

## Tips

1. **Use TypeScript's inference**: You don't always need explicit types
2. **Start with any, then refine**: Better to have working code than perfect types
3. **Export types**: Always export interfaces/types from components
4. **Use generics for reusable hooks**: Like `useFetch<User>(url)`
5. **Type your API responses**: Create interfaces for all API data
6. **Leverage union types**: For variants, sizes, states, etc.
7. **Keep Storybook working**: Update stories to .tsx as you migrate components

## Common Pitfalls

- Don't migrate everything at once
- Don't obsess over perfect types initially
- Don't forget to update imports when renaming files
- Do test each component after migration
- Do commit after each successful component migration
- Do keep your development server running to catch errors early