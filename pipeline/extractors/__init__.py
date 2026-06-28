from .caterpillar import extract_pdf as extract_caterpillar
from .hitachi import extract_pdf as extract_hitachi

EXTRACTORS = {
    "caterpillar": extract_caterpillar,
    "hitachi": extract_hitachi,
}
