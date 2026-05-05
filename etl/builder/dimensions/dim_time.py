import pandas as pd
from datetime import datetime, timedelta
import logging
from ..base_builder import BaseBuilder

logger = logging.getLogger(__name__)

class TimeDimensionBuilder(BaseBuilder):

    def __init__(self, output_path: str = "data/warehouse"):
        super().__init__(output_path)

    def generate_time_dimension(self, start_date: str = "2020-01-01", 
                              end_date: str = "2030-12-31") -> pd.DataFrame:
        logger.info("Generating time dimension...")
        
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        dates = pd.date_range(start, end, freq='D')
        
        time_dim = pd.DataFrame({
            'date_key': dates.date,
            'year': dates.year,
            'quarter': 'Q' + dates.quarter.astype(str),
            'month_num': dates.month,
            'month_name': dates.strftime('%B'),
            'week_of_year': dates.isocalendar().week,
            'day_of_week': dates.strftime('%A'),
            'is_weekend': dates.dayofweek >= 5,
        })
        
        return time_dim

    def build(self, start_date: str = "2020-01-01", end_date: str = "2030-12-31") -> pd.DataFrame:
        return self.generate_time_dimension(start_date, end_date)
