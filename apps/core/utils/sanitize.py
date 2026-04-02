"""
HTML Sanitization utilities using bleach.

Removes dangerous HTML tags and attributes while preserving safe formatting.
Use this to sanitize any user-provided HTML content before storing or rendering.
"""
import bleach

# Allowed HTML tags (safe for rendering)
ALLOWED_TAGS = [
    # Basic formatting
    'p', 'br', 'strong', 'em', 'u', 'b', 'i',
    # Lists
    'ul', 'ol', 'li',
    # Headings
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    # Links
    'a',
    # Line breaks
    'hr',
]

# Allowed HTML attributes per tag
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel'],  # Links with href only
    '*': ['class'],  # Allow class on all tags (for styling)
}

# Allowed protocols for links
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def sanitize_html(html: str) -> str:
    """
    Remove dangerous HTML tags and attributes.

    Args:
        html: Raw HTML string from user input

    Returns:
        Sanitized HTML string safe for rendering

    Example:
        >>> sanitize_html('<p>Hello</p><script>alert("xss")</script>')
        '<p>Hello</p>alert("xss")'

        >>> sanitize_html('<a href="javascript:alert()">Click</a>')
        '<a>Click</a>'
    """
    if not html:
        return ""

    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,  # Strip disallowed tags instead of escaping
    )


def sanitize_text(text: str) -> str:
    """
    Remove ALL HTML tags from text.
    Use this for fields that should contain plain text only.

    Args:
        text: Text that may contain HTML

    Returns:
        Plain text with all HTML removed

    Example:
        >>> sanitize_text('Hello <b>World</b>')
        'Hello World'
    """
    if not text:
        return ""

    return bleach.clean(text, tags=[], strip=True)


def truncate_html(html: str, max_length: int = 200) -> str:
    """
    Truncate HTML to max_length characters while preserving valid HTML.

    Args:
        html: HTML string to truncate
        max_length: Maximum length in characters

    Returns:
        Truncated HTML with properly closed tags
    """
    if not html:
        return ""

    # First sanitize
    clean = sanitize_html(html)

    # Then truncate if needed
    if len(clean) <= max_length:
        return clean

    return clean[:max_length] + "..."
