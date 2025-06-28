-- Create remaining critical performance indexes
-- Execute each index separately to avoid parsing issues

-- MEMBER_ROLES TABLE INDEXES
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_member_roles_expiry_not_null 
    ON member_roles(expiration_date) 
    WHERE expiration_date IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_member_roles_active 
    ON member_roles(member_id, role_id) 
    WHERE expiration_date IS NULL OR expiration_date > NOW();

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_member_roles_member_id 
    ON member_roles(member_id);

-- ACTIVITY TABLE INDEXES  
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_leaderboard 
    ON activity(date, activity_type, member_id, points);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_member_date 
    ON activity(member_id, date DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_date_type_points 
    ON activity(date, activity_type, points);

-- INVITES TABLE INDEXES
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invites_creator_stats 
    ON invites(creator_id, uses, created_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invites_usage_tracking 
    ON invites(last_used_at DESC) WHERE last_used_at IS NOT NULL;

-- NOTIFICATION_LOGS TABLE INDEXES
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_logs_member_tag 
    ON notification_logs(member_id, notification_tag);

-- MODERATION_LOGS TABLE INDEXES
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_moderation_logs_target_created 
    ON moderation_logs(target_user_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_moderation_logs_active 
    ON moderation_logs(target_user_id, expires_at) 
    WHERE expires_at IS NULL OR expires_at > NOW();

-- MESSAGES TABLE INDEXES
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_author_timestamp 
    ON messages(author_id, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_channel_timestamp 
    ON messages(channel_id, timestamp DESC);

-- MEMBERS TABLE INDEXES
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_members_voice_bypass 
    ON members(voice_bypass_until) WHERE voice_bypass_until IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_members_first_inviter 
    ON members(first_inviter_id) WHERE first_inviter_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_members_joined_at 
    ON members(joined_at) WHERE joined_at IS NOT NULL;

-- ROLES TABLE INDEXES
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_roles_type_name 
    ON roles(role_type, name);