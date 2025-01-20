from services.db_connection import PostgreSQLConnectionSingleton

class UWBRepository:
    def __init__(self):
        self.connection = PostgreSQLConnectionSingleton().get_connection()
        self.cursor = self.connection.cursor()

    def store_data(self, tag_id, x_position, y_position, timestamp):
        query = """
        INSERT INTO uwb_raw (tag_id, x_position, y_position, timestamp) VALUES (%s, %s, %s, %s)
        """
        self.cursor.execute(query, (tag_id, x_position, y_position, timestamp))
        self.connection.commit()

    def get_tag_info(self, tag_id):

        query = "SELECT tag_id, kube_id, nuc_id FROM uwb_tag WHERE tag_id = %s"
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, (tag_id,))
                return cursor.fetchone()
        except Exception as e:
            print(f"Error fetching tag info: {e}")
            return None
    
    def get_all_tag_info(self):

        query = "SELECT tag_id, kube_id, nuc_id FROM uwb_tag"
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            print(f"Error fetching all tag info: {e}")
            return []

    def close(self):
        """Closes the cursor and the database connection."""
        self.cursor.close()
        self.connection.close()