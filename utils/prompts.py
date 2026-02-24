# utils/prompts.py

TWITTER_PROMPT_SHORT = """
Here are my thoughts collected throughout the day:

{thoughts}

Please generate Twitter/X posts based on these thoughts, following these specific guidelines:

1. Each post must be between {min_chars} and {max_chars} characters (typically up to 280 characters).
2. If the thoughts are closely related, combine them into a single cohesive post rather than creating separate posts.
3. Maintain the same tone, style and perspective as the original thoughts - do not add your own opinions or deviate from the sentiment expressed.
4. Make the posts conversational and insightful, ready to publish.
5. do not include hashtags at the end of the post.
6. Focus on the most interesting or profound ideas from the thoughts.
7. If there is a word that is not a word, use the same spelling as the original thought.
8. Return 3 post options to choose from.

Return your response as a JSON array of posts, following this format exactly and make sure that it is valid JSON:
```json
[
  {{
    "post_text": "First post content here",
    "topics": ["topic1", "topic2"],
    "character_count": 123
  }},
  {{
    "post_text": "Second post content",
    "topics": ["topic3"],
    "character_count": 98
  }}
]
```

Return ONLY the JSON array with no additional text, explanations, or formatting.
"""

TWITTER_PROMPT_MEDIUM = """
Here are my thoughts collected throughout the day:

{thoughts}

Please generate medium-length Twitter/X posts based on these thoughts, following these specific guidelines:

1. Each post must be between {min_chars} and {max_chars}.
2. Synthesize and combine related thoughts into cohesive posts. Elaborate slightly where appropriate to add depth, but stay concise.
3. Maintain the same tone, style and perspective as the original thoughts - do not add your own opinions or deviate from the sentiment expressed.
4. Make the posts conversational and insightful, suitable for a slightly longer format.
5. do not include hashtags at the end of the post.
6. Focus on developing the most interesting or profound ideas from the thoughts into slightly more detailed posts.
7. If there is a word that is not a word, use the same spelling as the original thought.
8. Return 2-3 post options to choose from.

Return your response as a JSON array of posts, following this format exactly and make sure that it is valid JSON:
```json
[
  {{
    "post_text": "First medium post content here, potentially combining several thoughts...",
    "topics": ["topic1", "topic2", "related_topic"],
    "character_count": 450
  }},
  {{
    "post_text": "Second medium post content here...",
    "topics": ["topic3", "another_topic"],
    "character_count": 310
  }}
]
```

Return ONLY the JSON array with no additional text, explanations, or formatting.
"""

TWITTER_PROMPT_LONG = """
Here are my thoughts collected throughout the day:

{thoughts}

Please generate longer-form Twitter/X posts or mini-threads based on these thoughts, following these specific guidelines:

1. Each post (or the total text if a single post) must be between {min_chars} and {max_chars} characters.
2. Synthesize the core ideas from the thoughts into a detailed narrative, summary, or exploration. Combine related concepts extensively.
3. Maintain the same tone, style and perspective as the original thoughts - do not add your own opinions or deviate from the sentiment expressed.
4. Structure the output logically, suitable for a longer read. If creating a thread, indicate breaks clearly if possible within the JSON structure (though the primary goal is the text content).
5. Include 2-3 relevant hashtags at the end of the post or the final tweet in a thread.
6. Focus on providing a comprehensive and insightful take on the main themes present in the thoughts.
7. If there is a word that is not a word, use the same spelling as the original thought.
8. Return 1-2 post options to choose from.

Return your response as a JSON array of posts, following this format exactly and make sure that it is valid JSON:
```json
[
  {{
    "post_text": "A longer-form post synthesizing multiple thoughts into a coherent narrative or analysis... This could potentially be structured as a thread, but the full text is provided here.",
    "topics": ["main_theme", "sub_topic1", "sub_topic2"],
    "character_count": 1500
  }}
]
```

Return ONLY the JSON array with no additional text, explanations, or formatting.
"""
