import os
import sys
from PIL import Image

# Add parent dir to path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from main import design_pin_image

def create_dummy_image(output_path):
    img = Image.new("RGB", (768, 1024), color=(100, 150, 200))
    img.save(output_path)
    return output_path

if __name__ == "__main__":
    scratch_dir = os.path.dirname(__file__)
    dummy_img = create_dummy_image(os.path.join(scratch_dir, "dummy_bg.jpg"))
    
    # We will temporarily patch random.choice to force layouts
    import random
    original_choice = random.choice
    
    layouts = ['bottom_fade', 'center_box', 'top_fade', 'solid_block']
    
    for layout in layouts:
        print(f"Testing layout: {layout}")
        
        def forced_choice(seq):
            if set(seq) == set(layouts):
                return layout
            return original_choice(seq)
            
        random.choice = forced_choice
        
        # Call the design function
        design_pin_image(
            dummy_img, 
            "The Secret To This Viral Minimalist Look", 
            scratch_dir
        )
        
        # Rename the output so it doesn't get overwritten
        os.rename(
            os.path.join(scratch_dir, "final_pin.jpg"),
            os.path.join(scratch_dir, f"test_layout_{layout}.jpg")
        )
    
    print("Test complete. Check the scratch directory for images.")
