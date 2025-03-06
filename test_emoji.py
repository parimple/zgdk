import emoji

def emoji_validator_v1(emoji_str):
    """Stara wersja walidatora emoji"""
    if not emoji_str:
        return False

    # Check if it's a standard Unicode emoji using the emoji library
    if emoji.is_emoji(emoji_str):
        return True
    
    # Check for Discord custom emoji format: <:name:id> or <a:name:id>
    if emoji_str.startswith("<") and emoji_str.endswith(">"):
        parts = emoji_str.strip("<>").split(":")
        return len(parts) >= 2 and all(part for part in parts)
    
    return False

def emoji_validator_v2(emoji_str):
    """Nowa wersja walidatora emoji"""
    if not emoji_str: 
        return False
    
    # Check if it's a standard Unicode emoji using the emoji library
    if emoji.is_emoji(emoji_str):
        return True
    
    # Check if it's a valid custom emoji
    if emoji_str.startswith('<') and emoji_str.endswith('>'):
        parts = emoji_str.strip('<>').split(':')
        
        # For emojis in format <:name:id> we have ['', 'name', 'id']
        # For emojis in format <a:name:id> we have ['a', 'name', 'id']
        # Make sure we have at least 3 parts and the second and third are not empty
        if len(parts) >= 3 and parts[1] and parts[2]:
            return True
        
        # For other formats, check if all parts are non-empty
        return len(parts) >= 2 and all(part for part in parts)
    
    return False

# Test cases
test_cases = [
    '<:Bohun:1072975167258628146>',
    '<a:spinning:123456789>',
    '<::1234>',
    '<:>',
    '<1234>',
    '😀',
    '🤑',
    ':Bohun:'
]

# Run tests
print("Comparing old and new emoji validator:")
print("=====================================")
for test in test_cases:
    parts = test.strip('<>').split(':') if test.startswith('<') and test.endswith('>') else []
    v1_result = emoji_validator_v1(test)
    v2_result = emoji_validator_v2(test)
    improved = "✅" if not v1_result and v2_result else "❌" if v1_result and not v2_result else "  "
    print(f'Emoji: {test:25} Old: {v1_result!s:5} New: {v2_result!s:5} {improved} Parts: {parts}') 