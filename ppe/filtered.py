# ============================================================
# FILTER PPE DATASET
# REMOVE:
# - no-helmet
# - no-vest
#
# KEEP ONLY:
# 0 -> helmet
# 1 -> person
# 2 -> vest
# ============================================================

import os
import shutil
from glob import glob

# ============================================================
# ORIGINAL DATASET PATH
# ============================================================

DATASET_PATH="Worker-Safety.v1-workersafety.yolov8"

# ============================================================
# NEW FILTERED DATASET PATH
# ============================================================

NEW_DATASET="ppe_filtered"

os.makedirs(NEW_DATASET,exist_ok=True)

# ============================================================
# DATASET SPLITS
# ============================================================

splits=["train","valid","test"]

# ============================================================
# OLD CLASSES
# ============================================================

# 0 -> helmet
# 1 -> no-helmet (REMOVE)
# 2 -> no-vest   (REMOVE)
# 3 -> person
# 4 -> vest

# ============================================================
# NEW CLASS MAPPING
# ============================================================

class_map={
    0:0,   # helmet -> helmet
    3:1,   # person -> person
    4:2    # vest -> vest
}

# ============================================================
# PROCESS EACH SPLIT
# ============================================================

for split in splits:

    print(f"\nPROCESSING {split.upper()} SET")

    image_src=os.path.join(DATASET_PATH,split,"images")
    label_src=os.path.join(DATASET_PATH,split,"labels")

    image_dst=os.path.join(NEW_DATASET,split,"images")
    label_dst=os.path.join(NEW_DATASET,split,"labels")

    os.makedirs(image_dst,exist_ok=True)
    os.makedirs(label_dst,exist_ok=True)

    image_files=glob(os.path.join(image_src,"*.*"))

    print("Total Images:",len(image_files))

    # ========================================================
    # PROCESS EACH IMAGE
    # ========================================================

    for img_path in image_files:

        filename=os.path.basename(img_path)

        # ====================================================
        # COPY IMAGE
        # ====================================================

        shutil.copy(img_path,image_dst)

        # ====================================================
        # ORIGINAL LABEL PATH
        # ====================================================

        label_path=os.path.join(
            label_src,
            os.path.splitext(filename)[0]+".txt"
        )

        new_lines=[]

        # ====================================================
        # PROCESS LABELS
        # ====================================================

        if os.path.exists(label_path):

            with open(label_path,"r") as f:
                lines=f.readlines()

            for line in lines:

                vals=line.strip().split()

                if len(vals)!=5:
                    continue

                cls=int(vals[0])

                # ============================================
                # KEEP ONLY helmet/person/vest
                # ============================================

                if cls in class_map:

                    new_cls=class_map[cls]

                    vals[0]=str(new_cls)

                    new_lines.append(" ".join(vals))

        # ====================================================
        # SAVE FILTERED LABEL FILE
        # ====================================================

        new_label_path=os.path.join(
            label_dst,
            os.path.splitext(filename)[0]+".txt"
        )

        with open(new_label_path,"w") as f:

            for line in new_lines:
                f.write(line+"\n")

print("\nFILTERED DATASET CREATED SUCCESSFULLY")

# ============================================================
# CREATE NEW YAML FILE
# ============================================================

yaml_content="""
train: ../train/images
val: ../valid/images
test: ../test/images

nc: 3

names:
  0: helmet
  1: person
  2: vest
"""

yaml_path=os.path.join(NEW_DATASET,"data.yaml")

with open(yaml_path,"w") as f:
    f.write(yaml_content)

print("\nNEW YAML FILE CREATED")

print(yaml_path)

for split in splits:

    img_count=len(
        glob(os.path.join(
            NEW_DATASET,
            split,
            "images",
            "*.*"
        ))
    )

    label_count=len(
        glob(os.path.join(
            NEW_DATASET,
            split,
            "labels",
            "*.txt"
        ))
    )

    print(f"\n{split.upper()}")

    print("Images:",img_count)

    print("Labels:",label_count)

print("\nREADY FOR YOLO TRAINING")