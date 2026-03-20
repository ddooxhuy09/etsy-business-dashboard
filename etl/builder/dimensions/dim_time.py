"""
Time Dimension Builder
Generates comprehensive time dimension table with Etsy business calendar
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import List
from ..base_builder import BaseBuilder

logger = logging.getLogger(__name__)

class TimeDimensionBuilder(BaseBuilder):
    """Build time dimension with Etsy business calendar"""
    
    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def generate_time_dimension(self, start_date: str = "2020-01-01", 
                              end_date: str = "2030-12-31") -> pd.DataFrame:
        """Generate comprehensive time dimension table"""
        logger.info("Generating time dimension...")
        
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        dates = pd.date_range(start, end, freq='D')
        
        time_dim = pd.DataFrame({
            'time_key': dates.strftime('%Y%m%d').astype(int),
            'full_date': dates.date,
            'year': dates.year,
            'quarter': dates.quarter,
            'month': dates.month,
            'week_of_year': dates.isocalendar().week,
            'day_of_month': dates.day,
            'day_of_week': dates.dayofweek + 1,  # Monday = 1
            'day_of_year': dates.dayofyear,
            'month_name': dates.strftime('%B'),
            'day_name': dates.strftime('%A'),
            'quarter_name': 'Q' + dates.quarter.astype(str),
            'is_weekend': dates.dayofweek >= 5,
            'is_business_day': (dates.dayofweek < 5) & (~dates.isin(self._get_holidays(dates))),
        })
        
        # Add Etsy business calendar
        time_dim['etsy_season'] = time_dim['month'].map(self._get_etsy_season)
        time_dim['is_peak_season'] = time_dim['month'].isin([11, 12, 1, 2])  # Holiday season
        time_dim['selling_season'] = time_dim['month'].map(self._get_selling_season)
        
        # Current period flags
        today = datetime.now().date()
        time_dim['is_current_day'] = time_dim['full_date'] == today
        time_dim['is_current_week'] = (
            (time_dim['full_date'] >= today - timedelta(days=today.weekday())) &
            (time_dim['full_date'] < today + timedelta(days=7-today.weekday()))
        )
        time_dim['is_current_month'] = (
            (time_dim['year'] == today.year) & 
            (time_dim['month'] == today.month)
        )
        time_dim['is_current_quarter'] = (
            (time_dim['year'] == today.year) & 
            (time_dim['quarter'] == (today.month - 1) // 3 + 1)
        )
        time_dim['is_current_year'] = time_dim['year'] == today.year
        
        return time_dim

    def build(self, start_date: str = "2020-01-01", end_date: str = "2030-12-31") -> pd.DataFrame:
        """Main build method for time dimension"""
        time_dim = self.generate_time_dimension(start_date, end_date)
        return time_dim
