import omni.graph.core as og

class WheelbaseProvider:
    @staticmethod
    def compute(db: og.Database) -> bool:

        db.outputs.wheelbase_value = 0.512 # 출력 속성 이름: wheelbase_value
        return True