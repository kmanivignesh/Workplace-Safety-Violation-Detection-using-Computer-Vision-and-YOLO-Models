import os
from pathlib import Path

def delete_unlabeled_images(base_path, splits=['train', 'valid', 'test']):
    """
    Deletes images that have no corresponding label file or empty label file.
    Also deletes the empty label files to keep the folder clean.
    """
    for split in splits:
        images_dir = Path(base_path) / split / 'images'
        labels_dir = Path(base_path) / split / 'labels'
        
        if not images_dir.exists() or not labels_dir.exists():
            print(f"⚠️ Skipping {split}: images or labels folder missing")
            continue
        
        # Get all image files (supports .jpg, .png, .jpeg)
        image_files = list(images_dir.glob('*.*'))
        print(f"\n📂 {split}: found {len(image_files)} images")
        
        removed_count = 0
        for img_file in image_files:
            label_file = labels_dir / (img_file.stem + '.txt')
            
            # Check if label file exists and is not empty
            keep = False
            if label_file.exists():
                # Check if file has any content (non‑zero size and contains numbers)
                if label_file.stat().st_size > 0:
                    with open(label_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            keep = True
            
            if not keep:
                # Delete the image
                os.remove(img_file)
                removed_count += 1
                # Also delete empty label file if it exists
                if label_file.exists() and label_file.stat().st_size == 0:
                    os.remove(label_file)
                # Optional: print deleted file name (use for debugging)
                # print(f"   Deleted: {img_file.name}")
        
        print(f"   Deleted {removed_count} images without labels")
        
        # Count remaining images
        remaining = len(list(images_dir.glob('*.*')))
        print(f"   Remaining images: {remaining}")

# ============================================
# CONFIGURATION
# ============================================
# Change this to your dataset folder path
base_path = "Smoking.v3i.yolov8"   # or "/kaggle/input/.../Smoking.v3i.yolov8"

# Run deletion
delete_unlabeled_images(base_path)