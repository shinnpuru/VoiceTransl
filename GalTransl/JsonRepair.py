"""Conservative repair of complete translation objects with damaged endings."""
import json
import re


def load_translation_object(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError as original:
        # Only repair the final delimiter. Never fill in truncated dialogue or IDs.
        stripped = text.rstrip()
        candidates = [stripped + '}']
        smart_end = re.search(r'”\s*\}?$', stripped)
        if smart_end:
            candidates.append(stripped[:smart_end.start()] + '"}')
        for candidate in candidates:
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
        raise original
