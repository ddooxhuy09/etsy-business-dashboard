"""
Listing Data Processor - Clean and Load to PostgreSQL
Process listing data for dim_listing table
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging
import re


from etl.utils_core import setup_logging, convert_columns_to_snake_case, ensure_proper_data_types

def clean_listing_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean listing data for database loading"""
    logger = setup_logging()
    logger.info("🔄 Cleaning listing data...")
    
    df_clean = df.copy()
    # Split list-like columns
    if 'TAGS' in df_clean.columns:
        df_clean['tags_list'] = df_clean['TAGS'].astype(str).where(~df_clean['TAGS'].isna(), '').str.split(',')
    if 'MATERIALS' in df_clean.columns:
        df_clean['materials_list'] = df_clean['MATERIALS'].astype(str).where(~df_clean['MATERIALS'].isna(), '').str.split(',')
    if 'SKU' in df_clean.columns:
        df_clean['SKU'] = df_clean['SKU'].astype(str).where(~df_clean['SKU'].isna(), '').str.split(',')

    # Clean and parse description
    if 'DESCRIPTION' in df_clean.columns:
        df_clean['DESCRIPTION_clean'] = df_clean['DESCRIPTION'].apply(clean_description)
        parsed_df = df_clean['DESCRIPTION_clean'].apply(parse_description)
        # Combine parsed fields back to main df
        df_clean = pd.concat([df_clean, parsed_df], axis=1)

    # Convert column names to snake_case
    df_clean = convert_columns_to_snake_case(df_clean)
    
    # Ensure proper data types for Parquet
    df_clean = ensure_proper_data_types(df_clean, 'listing')

    return df_clean


def clean_description(desc: str) -> str:
    if pd.isna(desc):
        return ''
    lines = str(desc).split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if (
            'Orders placed after' in line
            or 'WE HAVE DISCOUNT' in line
            or 'We also have discount' in line
            or 'WE OFFER BULK ORDER' in line
            or 'please note if you want to order large quantity' in line
            or 'If you need any else' in line
            or 'Thank you.' in line
            or 'If you have any querries' in line
            or 'please kindly message us' in line
        ):
            continue
        if (
            'Proud to be made in Viet Nam' in line
            or 'Made In Viet Nam' in line
            or 'Proud to be made in Vietnam.' in line
            or 'Proudly made in Vietnam.' in line
        ):
            # Remove it, since we have Country column
            continue
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)


def parse_description(desc: str) -> pd.Series:
    if pd.isna(desc):
        return pd.Series({})
    story = []
    material = ''
    dimensions = ''
    color = ''
    how_made = ''
    package = ''
    instructions = ''
    how_use = ''
    fit_for = ''
    note = ''

    flags = re.IGNORECASE | re.DOTALL | re.MULTILINE

    # Terminator for sections
    terminator = r'(?=\n\s*-|\n\s*Material|\n\s*Color|\n\s*HOW|\n\s*Product package|\n\s*Proudly|\n\s*Fit for|\n\s*How to|\n\s*Package|\n\s*Hand Fan Dimension|\n\s*\* Instructions|\n\s*Kindly note|\s*$)'

    text = str(desc)

    # Extract material
    material_match = re.search(r'^(?:- )?Material:\s*(.*?)' + terminator, text, flags)
    if material_match:
        material = material_match.group(1).strip().replace('\n', ' ')

    # Extract dimensions
    dimensions_match = re.search(r'^(?:- )?(?:Product dimension|Dimension|Hand Fan Dimension|DIMENSION):\s*(.*?)' + terminator, text, flags)
    if dimensions_match:
        dimensions = dimensions_match.group(1).strip().replace('\n', ' ')
    else:
        dimensions_match = re.search(r'^(?:- )?(?:Product dimension|Dimension|Hand Fan Dimension|DIMENSION):\s*(.*)$', text, flags)
        if dimensions_match:
            dimensions = dimensions_match.group(1).strip().replace('\n', ' ')

    # Extract color
    color_match = re.search(r'^(?:- )?Color:\s*(.*?)' + terminator, text, flags)
    if color_match:
        color = color_match.group(1).strip().replace('\n', ' ')

    # Extract how made
    how_made_match = re.search(r'^(?:- )?(?:How was it made|How it was made|HOW IT WAS MADE):\s*(.*?)' + terminator, text, flags)
    if how_made_match:
        how_made = how_made_match.group(1).strip().replace('\n', ' ')

    # Extract package
    package_match = re.search(r'^(?:- )?Product package:\s*(.*?)' + terminator, text, flags)
    if package_match:
        package = package_match.group(1).strip().replace('\n', ' ')
    else:
        package_match = re.search(r'^Package:\s*(.*?)' + terminator, text, flags)
        if package_match:
            package = package_match.group(1).strip().replace('\n', ' ')

    # Extract instructions
    instructions_match = re.search(r'^\* Instructions for use and care:\s*(.*?)' + terminator, text, flags)
    if instructions_match:
        instructions = instructions_match.group(1).strip().replace('\n', ' ')
    else:
        instructions_match = re.search(r'^\- The product should be kept in a dry place\.(.*?)' + terminator, text, flags)
        if instructions_match:
            instructions = instructions_match.group(1).strip().replace('\n', ' ')

    # Extract how to use/refill
    how_use_match = re.search(r'^(?:- )?(?:How to use|How to refill):\s*(.*?)' + terminator, text, flags)
    if how_use_match:
        how_use = how_use_match.group(1).strip().replace('\n', ' ')

    # Extract fit for
    fit_for_match = re.search(r'^Fit for standard tissue box\s*(.*?)' + terminator, text, flags)
    if fit_for_match:
        fit_for = fit_for_match.group(1).strip().replace('\n', ' ')

    # Extract note
    note_match = re.search(r'^Kindly note since this is a handmade product, the size will vary from \+-2 cm\. Please read carefully about the size before making your purchase\.', text, flags)
    if note_match:
        note = 'Handmade product, size may vary ±2 cm.'

    # Extract story (text before structured sections)
    structured_start = re.search(r'^(Dimension|DIMENSION|- Dimension|- Material|Material|Hand Fan Dimension|- Product dimension|- How|Fit for|Package|- Color|HOW IT WAS MADE|\* Instructions)', text, flags)
    if structured_start:
        story_text = text[:structured_start.start()].strip()
    else:
        story_text = text.strip()

    story = '\n'.join([line.strip() for line in story_text.split('\n') if line.strip()])

    return pd.Series(
        {
            'Story': story,
            'Material': material,
            'Dimensions': dimensions,
            'Color': color,
            'How_Made': how_made,
            'Package': package,
            'Instructions': instructions,
            'How_Use': how_use,
            'Fit_For': fit_for,
            'Note': note,
            'Country': 'Vietnam',
        }
    )