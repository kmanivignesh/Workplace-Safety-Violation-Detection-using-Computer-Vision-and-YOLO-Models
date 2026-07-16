import os
from pathlib import Path

def remove_class_and_reindex(label_dir):
    for label_file in Path(label_dir).glob("*.txt"):
        lines = []
        with open(label_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                class_id = int(parts[0])
                if class_id == 1:   # keep only 'smoking' (original class 1)
                    parts[0] = '0'  # re-index to 0
                    lines.append(" ".join(parts))
        if lines:
            with open(label_file, 'w') as f:
                f.write("\n".join(lines))
        else:
            # No smoking annotations → remove the label file
            os.remove(label_file)
            # Optional: also remove corresponding image
            # img_file = label_file.with_suffix('.jpg')
            # if img_file.exists(): os.remove(img_file)

# Run for each split – UPDATE THESE PATHS to match your actual location
base_path = "Smoking.v3i.yolov8"   # or full path like "./Smoking.v3i.yolov8"

for split in ['train', 'valid', 'test']:
    label_dir = os.path.join(base_path, split, 'labels')
    if os.path.exists(label_dir):
        remove_class_and_reindex(label_dir)
        print(f"Processed {label_dir}")
    else:
        print(f"Warning: {label_dir} not found")