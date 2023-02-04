import datetime
import logging
import sqlite3
import threading
from enum import Enum

from src.app.Component import Component


class MetricCollectionMode:
    TO_DB = 'd'
    SEND = 's'
    TO_STDOUT = 'l'


# Parent class for metric collectors
class Metric(threading.Thread):
    result = None

    def __init__(self, components: [Component], elapsed_time):
        super().__init__()
        self.components = components
        self.elapsed_time = elapsed_time

    def run(self):
        pass


# Manages running metric collector threads
class MetricCollector:
    def __init__(self, metric_type, components, mode: str, db_cursor: sqlite3.Cursor):
        self.metric_type = metric_type
        self.metric_thread = None
        self.mode = mode
        self.components = components
        self.db = db_cursor

    def collect(self, elapsed_time):
        self.metric_thread = self.metric_type(self.components, elapsed_time)
        self.metric_thread.start()

    def process_results(self):
        self.metric_thread.join()
        # Collect the metric
        collected_result = self.metric_thread.result

        if self.mode.__contains__(MetricCollectionMode.TO_STDOUT):
            logging.info(f"{self.metric_thread.name} - {self.metric_thread.elapsed_time} - {collected_result}")
        if self.mode.__contains__(MetricCollectionMode.SEND):
            # TODO Send the results as a message to the server immediately
            pass
        if self.mode.__contains__(MetricCollectionMode.TO_DB):
            try:
                self.db.executemany(self.metric_thread.db_query_template, collected_result)
            except sqlite3.Error as error:
                logging.error(error)
