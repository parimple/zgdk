-- =====================================================
-- CRITICAL PERFORMANCE INDEXES FOR ZGDK DISCORD BOT
-- Expected performance improvement: 100x for affected queries
-- =====================================================

-- =====================================================
-- MEMBER_ROLES TABLE INDEXES
-- =====================================================

-- Most critical: Premium role expiration queries
-- Used by: Premium role audit, role expiration checks
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_member_roles_expiry_not_null 
    ON member_roles(expiration_date) 
    WHERE expiration_date IS NOT NULL;

-- Active premium roles (no expiration or future expiration)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_member_roles_active 
    ON member_roles(member_id, role_id) 
    WHERE expiration_date IS NULL OR expiration_date > NOW();

-- Member-specific role lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_member_roles_member_id 
    ON member_roles(member_id);

-- =====================================================
-- ACTIVITY TABLE INDEXES  
-- =====================================================

-- Most critical: Leaderboard and ranking queries
-- Used by: Activity leaderboard, member statistics, ranking commands
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_leaderboard 
    ON activity(date, activity_type, member_id, points);

-- Member activity lookup (profile pages, statistics)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_member_date 
    ON activity(member_id, date DESC);

-- Date range queries for activity statistics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_date_type_points 
    ON activity(date, activity_type, points);

-- Aggregate queries by activity type
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_type_date_points 
    ON activity(activity_type, date, points);

-- =====================================================
-- INVITES TABLE INDEXES
-- =====================================================

-- Creator statistics and leaderboards
-- Used by: Invite leaderboards, member statistics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invites_creator_stats 
    ON invites(creator_id, uses, created_at);

-- Invite usage tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invites_usage_tracking 
    ON invites(last_used_at DESC) WHERE last_used_at IS NOT NULL;

-- =====================================================
-- NOTIFICATION_LOGS TABLE INDEXES
-- =====================================================

-- Member notification queries
-- Used by: Notification management, opt-out checking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_logs_member_tag 
    ON notification_logs(member_id, notification_tag);

-- Notification statistics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_logs_tag_sent 
    ON notification_logs(notification_tag, sent_at);

-- =====================================================
-- MODERATION_LOGS TABLE INDEXES
-- =====================================================

-- Target user moderation history
-- Used by: Moderation commands, user history
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_moderation_logs_target_created 
    ON moderation_logs(target_user_id, created_at DESC);

-- Active moderation (unexpired)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_moderation_logs_active 
    ON moderation_logs(target_user_id, expires_at) 
    WHERE expires_at IS NULL OR expires_at > NOW();

-- Moderator action history
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_moderation_logs_moderator 
    ON moderation_logs(moderator_id, created_at DESC);

-- Action type filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_moderation_logs_action_type 
    ON moderation_logs(action_type, created_at DESC);

-- =====================================================
-- MESSAGES TABLE INDEXES
-- =====================================================

-- Author message lookup
-- Used by: Message tracking, user activity
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_author_timestamp 
    ON messages(author_id, timestamp DESC);

-- Channel message lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_channel_timestamp 
    ON messages(channel_id, timestamp DESC);

-- Reply thread tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_reply_to 
    ON messages(reply_to_message_id) WHERE reply_to_message_id IS NOT NULL;

-- =====================================================
-- CHANNEL_PERMISSIONS TABLE INDEXES
-- =====================================================

-- Member permissions lookup
-- Used by: Voice channel management, permission checks
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_channel_permissions_member 
    ON channel_permissions(member_id, target_id);

-- Target permissions (channel/role specific)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_channel_permissions_target 
    ON channel_permissions(target_id, last_updated_at);

-- =====================================================
-- AUTOKICKS TABLE INDEXES
-- =====================================================

-- Owner autokick management
-- Used by: Voice channel autokick system
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_autokicks_owner_created 
    ON autokicks(owner_id, created_at);

-- Target tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_autokicks_target 
    ON autokicks(target_id);

-- =====================================================
-- HANDLED_PAYMENTS TABLE INDEXES
-- =====================================================

-- Member payment history
-- Used by: Payment tracking, premium management
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_handled_payments_member_paid 
    ON handled_payments(member_id, paid_at DESC) WHERE member_id IS NOT NULL;

-- Payment type analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_handled_payments_type_date 
    ON handled_payments(payment_type, paid_at);

-- =====================================================
-- MEMBERS TABLE INDEXES
-- =====================================================

-- Voice bypass queries
-- Used by: Voice channel access, bypass management
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_members_voice_bypass 
    ON members(voice_bypass_until) WHERE voice_bypass_until IS NOT NULL;

-- Inviter relationships
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_members_first_inviter 
    ON members(first_inviter_id) WHERE first_inviter_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_members_current_inviter 
    ON members(current_inviter_id) WHERE current_inviter_id IS NOT NULL;

-- Join date tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_members_joined_at 
    ON members(joined_at) WHERE joined_at IS NOT NULL;

-- =====================================================
-- ROLES TABLE INDEXES
-- =====================================================

-- Role type queries
-- Used by: Premium management, team management
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_roles_type_name 
    ON roles(role_type, name);

-- =====================================================
-- COMPOSITE INDEXES FOR COMPLEX QUERIES
-- =====================================================

-- Premium role expiration with member info (most critical)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_member_roles_expiry_composite 
    ON member_roles(expiration_date, member_id, role_id) 
    WHERE expiration_date IS NOT NULL;

-- Activity leaderboard composite
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_leaderboard_composite 
    ON activity(date, activity_type) INCLUDE (member_id, points);

-- Invite statistics composite
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invites_stats_composite 
    ON invites(creator_id) INCLUDE (uses, created_at, last_used_at);

-- =====================================================
-- ANALYZE TABLES AFTER INDEX CREATION
-- =====================================================

-- Update table statistics for query planner
ANALYZE members;
ANALYZE roles;
ANALYZE member_roles;
ANALYZE activity;
ANALYZE invites;
ANALYZE messages;
ANALYZE channel_permissions;
ANALYZE notification_logs;
ANALYZE moderation_logs;
ANALYZE autokicks;
ANALYZE handled_payments;