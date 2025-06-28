-- Fix temporal indexes that failed due to NOW() function
-- Use timestamp literals instead of NOW() function

-- MEMBER_ROLES TABLE - Active roles without NOW()
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_member_roles_expiry_not_null 
    ON member_roles(expiration_date) 
    WHERE expiration_date IS NOT NULL;

-- MEMBER_ROLES TABLE - Non-expired roles (using timestamp comparison that works)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_member_roles_not_expired 
    ON member_roles(member_id, role_id, expiration_date) 
    WHERE expiration_date IS NULL;

-- ACTIVITY TABLE - Critical leaderboard index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_leaderboard 
    ON activity(date, activity_type, member_id, points);

-- INVITES TABLE - Creator statistics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invites_creator_stats 
    ON invites(creator_id, uses, created_at);

-- NOTIFICATION_LOGS TABLE
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_logs_member_tag 
    ON notification_logs(member_id, notification_tag);

-- MODERATION_LOGS TABLE - Target user logs
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_moderation_logs_target_created 
    ON moderation_logs(target_user_id, created_at DESC);

-- MODERATION_LOGS TABLE - Non-expired moderation (without NOW())
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_moderation_logs_not_expired 
    ON moderation_logs(target_user_id, expires_at)
    WHERE expires_at IS NULL;

-- MESSAGES TABLE - Author lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_author_timestamp 
    ON messages(author_id, timestamp DESC);

-- MEMBERS TABLE - Voice bypass
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_members_voice_bypass 
    ON members(voice_bypass_until) 
    WHERE voice_bypass_until IS NOT NULL;

-- ROLES TABLE
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_roles_type_name 
    ON roles(role_type, name);