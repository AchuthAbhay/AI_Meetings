from typing import List, Dict


def merge_whisper_with_diarization(
    whisper_segments: List[Dict],
    diarization_segments: List[Dict]
) -> List[Dict]:
    """
    Whisper ASR ke segments ko diarization (speaker info) ke saath merge karta hai.

    Returns:
    [
      {
        "speaker": "Speaker A",
        "start": 13.9,
        "end": 87.8,
        "text": "..."
      }
    ]
    """

    merged = []
    current_block = None

    for w in whisper_segments:               # Whisper ke har segment par iterate karte hain
        midpoint = (w["start"] + w["end"]) / 2
        speaker = "Unknown"

        for d in diarization_segments:
            if d["start"] <= midpoint <= d["end"]:
                speaker = d["speaker"]
                break

        if (
            current_block
            and current_block["speaker"] == speaker               # Agar same speaker continue ho raha hai, to text merge karo
        ):
            # Extend current speaker block
            current_block["end"] = w["end"]
            current_block["text"] += " " + w["text"]
        else:
            # Start new speaker block
            current_block = {                               # Naya speaker block start karo
                "speaker": speaker,
                "start": w["start"],
                "end": w["end"],
                "text": w["text"]
            }
            merged.append(current_block)

    return merged

