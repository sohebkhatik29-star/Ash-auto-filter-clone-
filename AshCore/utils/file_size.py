# Don't Remove Credit @movies_1780
# Subscribe YouTube Channel For Amazing Bot @tech_as_0
# Ask Doubt on telegram @movies_1780

def human_size(bytes, units=[' bytes','KB','MB','GB','TB', 'PB', 'EB']):
    """ Returns a human readable string representation of bytes """
    return str(bytes) + units[0] if int(bytes) < 1024 else human_size(int(bytes)>>10, units[1:])
