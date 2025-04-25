# setup.py
import os
from setuptools import setup, find_packages

# Function to read requirements
def read_requirements(filename="requirements.txt"):
    try:
        with open(os.path.join(os.path.dirname(__file__), filename), encoding="utf-8") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        print(f"Warning: {filename} not found. No requirements installed via setup.py.")
        return []

setup(
    name='VisionAIStudio', # Or your preferred package name
    version='0.1.0',
    # --- Tell find_packages where your source code is ---
    package_dir={'': '.'}, # Treat the current directory '.' as the root for packages
    packages=find_packages(where='.'), # Find packages starting from the current directory
    # --- ------------------------------------------- ---
    include_package_data=True, # Include non-code files specified in MANIFEST.in (if any)
    zip_safe=False,
    install_requires=read_requirements(), # Read from requirements.txt
    # Add entry points if you want command-line scripts
    # entry_points={
    #     'console_scripts': [
    #         'visionai=run:main', # Example if you had a main() in run.py
    #     ],
    # },
    python_requires='>=3.9', # Specify your Python version requirement
)