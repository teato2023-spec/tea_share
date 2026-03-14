"""
CMY 기반 유화 물감 혼합 시스템
Kubelka-Munk 모델을 활용한 물감 혼합 시뮬레이션
"""

import json
import math
from typing import Tuple, Dict, List
from dataclasses import dataclass


@dataclass
class Paint:
    """물감 정보"""
    name: str
    brand: str
    hex: str
    k: float
    s: float

    def rgb(self) -> Tuple[int, int, int]:
        """Hex -> RGB 변환"""
        hex_str = self.hex.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


class ColorConverter:
    """색 공간 변환 (RGB <-> CMY <-> Hex)"""

    @staticmethod
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """Hex -> RGB (0-255)"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def rgb_to_hex(r: int, g: int, b: int) -> str:
        """RGB (0-255) -> Hex"""
        return f'#{r:02X}{g:02X}{b:02X}'

    @staticmethod
    def rgb_to_cmy(r: int, g: int, b: int) -> Tuple[float, float, float]:
        """RGB (0-255) -> CMY (0-1)"""
        r_norm = r / 255.0
        g_norm = g / 255.0
        b_norm = b / 255.0

        c = 1 - r_norm
        m = 1 - g_norm
        y = 1 - b_norm

        return (c, m, y)

    @staticmethod
    def cmy_to_rgb(c: float, m: float, y: float) -> Tuple[int, int, int]:
        """CMY (0-1) -> RGB (0-255)"""
        r_norm = 1 - c
        g_norm = 1 - m
        b_norm = 1 - y

        r = int(max(0, min(255, r_norm * 255)))
        g = int(max(0, min(255, g_norm * 255)))
        b = int(max(0, min(255, b_norm * 255)))

        return (r, g, b)

    @staticmethod
    def rgb_to_kmtone(r: int, g: int, b: int) -> Tuple[float, float, float]:
        """RGB -> K/M/Y 톤 값 (0-1, 상대적 농도)"""
        c, m, y = ColorConverter.rgb_to_cmy(r, g, b)
        return (c, m, y)


class KubelkaMunk:
    """Kubelka-Munk 모델을 사용한 물감 혼합 계산"""

    @staticmethod
    def rgb_to_km(r: int, g: int, b: int) -> Tuple[float, float]:
        """
        RGB -> K(흡수계수), S(산란계수) 변환
        K: 빛 흡수 정도
        S: 빛 산란 정도
        """
        c, m, y = ColorConverter.rgb_to_cmy(r, g, b)

        avg_cmy = (c + m + y) / 3

        k = avg_cmy * 2.0

        s = (1 - avg_cmy) * 2.0 + 0.5

        return (k, s)

    @staticmethod
    def km_to_rgb(k: float, s: float) -> Tuple[int, int, int]:
        """
        K, S -> RGB 변환
        Kubelka-Munk 반사율 공식 사용
        """
        if s < 0.001:
            s = 0.001

        ks_ratio = k / s
        reflectance = 1 + ks_ratio - math.sqrt(ks_ratio**2 + 2*ks_ratio)

        reflectance = max(0, min(1, reflectance))

        gray_value = int(reflectance * 255)

        return (gray_value, gray_value, gray_value)

    @staticmethod
    def mix_paints(paint1: 'Paint', ratio1: float,
                   paint2: 'Paint', ratio2: float) -> Tuple[float, float]:
        """
        두 물감 혼합 후 K, S 계산
        paint1: 첫번째 물감
        ratio1: 첫번째 물감 비율 (0-1)
        paint2: 두번째 물감
        ratio2: 두번째 물감 비율 (0-1)
        """
        total_ratio = ratio1 + ratio2
        if total_ratio == 0:
            return (0, 0)

        ratio1 /= total_ratio
        ratio2 /= total_ratio

        k_mixed = paint1.k * ratio1 + paint2.k * ratio2
        s_mixed = paint1.s * ratio1 + paint2.s * ratio2

        return (k_mixed, s_mixed)


class PaintMixer:
    """물감 혼합 관리자"""

    def __init__(self):
        self.paints = {}
        self.converter = ColorConverter()
        self.km = KubelkaMunk()

    def add_paint(self, name: str, brand: str, hex_color: str):
        """물감 추가"""
        r, g, b = self.converter.hex_to_rgb(hex_color)
        k, s = self.km.rgb_to_km(r, g, b)
        paint = Paint(name=name, brand=brand, hex=hex_color, k=k, s=s)
        self.paints[f'{brand}_{name}'] = paint

    def list_paints(self) -> List[Dict]:
        """전체 물감 목록"""
        return [
            {
                'name': paint.name,
                'brand': paint.brand,
                'hex': paint.hex,
                'k': round(paint.k, 3),
                's': round(paint.s, 3),
            }
            for paint in self.paints.values()
        ]

    def mix_two_paints(self, paint1_id: str, ratio1: float,
                       paint2_id: str, ratio2: float) -> Dict:
        """두 물감 혼합"""
        if paint1_id not in self.paints or paint2_id not in self.paints:
            return {'error': '물감을 찾을 수 없습니다'}

        paint1 = self.paints[paint1_id]
        paint2 = self.paints[paint2_id]

        k_mixed, s_mixed = self.km.mix_paints(paint1, ratio1, paint2, ratio2)

        r, g, b = self.km.km_to_rgb(k_mixed, s_mixed)
        hex_result = self.converter.rgb_to_hex(r, g, b)

        return {
            'paint1': paint1.name,
            'ratio1': ratio1,
            'paint2': paint2.name,
            'ratio2': ratio2,
            'result_hex': hex_result,
            'result_rgb': [r, g, b],
            'result_k': round(k_mixed, 3),
            'result_s': round(s_mixed, 3),
        }

    def find_neutralizing_color(self, color_hex: str) -> Dict:
        """
        주어진 색과 혼합하면 무채색이 되는 색 찾기

        원리:
        - 입력 색의 CMY 값 계산
        - 무채색 조건: 보색 찾기
        - 라이브러리의 모든 물감 조합으로 가장 가까운 결과 찾기
        """
        r, g, b = self.converter.hex_to_rgb(color_hex)
        c, m, y = self.converter.rgb_to_cmy(r, g, b)

        ideal_c = 1 - c
        ideal_m = 1 - m
        ideal_y = 1 - y

        ideal_r, ideal_g, ideal_b = self.converter.cmy_to_rgb(ideal_c, ideal_m, ideal_y)
        ideal_hex = self.converter.rgb_to_hex(ideal_r, ideal_g, ideal_b)

        closest_paint = self._find_closest_paint(ideal_r, ideal_g, ideal_b)

        return {
            'input_hex': color_hex,
            'input_cmy': {'c': round(c, 3), 'm': round(m, 3), 'y': round(y, 3)},
            'ideal_complementary': {
                'hex': ideal_hex,
                'rgb': [ideal_r, ideal_g, ideal_b],
                'cmy': {'c': round(ideal_c, 3), 'm': round(ideal_m, 3), 'y': round(ideal_y, 3)},
            },
            'closest_paint_in_library': {
                'name': closest_paint.name if closest_paint else None,
                'brand': closest_paint.brand if closest_paint else None,
                'hex': closest_paint.hex if closest_paint else None,
            },
        }

    def _find_closest_paint(self, target_r: int, target_g: int, target_b: int) -> 'Paint':
        """라이브러리에서 목표 색과 가장 가까운 물감 찾기"""
        min_distance = float('inf')
        closest_paint = None

        for paint in self.paints.values():
            pr, pg, pb = paint.rgb()
            distance = math.sqrt(
                (pr - target_r)**2 +
                (pg - target_g)**2 +
                (pb - target_b)**2
            )

            if distance < min_distance:
                min_distance = distance
                closest_paint = paint

        return closest_paint

    def analyze_color(self, color_hex: str) -> Dict:
        """색 분석"""
        r, g, b = self.converter.hex_to_rgb(color_hex)
        c, m, y = self.converter.rgb_to_cmy(r, g, b)
        k, s = self.km.rgb_to_km(r, g, b)

        return {
            'hex': color_hex,
            'rgb': {'r': r, 'g': g, 'b': b},
            'cmy': {'c': round(c, 3), 'm': round(m, 3), 'y': round(y, 3)},
            'kubelka_munk': {'k': round(k, 3), 's': round(s, 3)},
            'characteristics': {
                'is_neutral': round(max(c, m, y) - min(c, m, y), 3) < 0.1,
                'dominant_channel': ['cyan', 'magenta', 'yellow'][[c, m, y].index(max(c, m, y))],
                'saturation': round(max(c, m, y), 3),
            },
        }


def demo():
    """데모 실행"""
    mixer = PaintMixer()

    mixer.add_paint('Cadmium Red', 'Winsor & Newton', '#E63946')
    mixer.add_paint('Alizarin Crimson', 'Winsor & Newton', '#C1121F')
    mixer.add_paint('Cadmium Yellow', 'Winsor & Newton', '#FFD60A')
    mixer.add_paint('French Ultramarine', 'Winsor & Newton', '#0066CC')
    mixer.add_paint('Titanium White', 'Winsor & Newton', '#FFFFFF')
    mixer.add_paint('Ivory Black', 'Winsor & Newton', '#000000')
    mixer.add_paint('Old Holland Blue', 'Old Holland', '#003366')

    print('=' * 60)
    print('CMY 기반 유화 물감 혼합 시스템')

    print('\n[등록된 물감]')
    for paint_info in mixer.list_paints():
        print(' - ' + paint_info['brand'] + ': ' + paint_info['name'] + ': ' + paint_info['hex'])

    print('\n[색 분석 예시]')
    test_color = '#FF6B9D'
    analysis = mixer.analyze_color(test_color)
    print('\n색: ' + test_color)
    print('RGB: R=' + str(analysis['rgb']['r']) + ', G=' + str(analysis['rgb']['g']) + ', B=' + str(analysis['rgb']['b']))
    print('CMY: C=' + str(analysis['cmy']['c']) + ', M=' + str(analysis['cmy']['m']) + ', Y=' + str(analysis['cmy']['y']))
    print('특성: ' + str(analysis['characteristics']))

    print('\n[혼합 예시]')
    result = mixer.mix_two_paints('Winsor & Newton_Cadmium Red', 1.0, 'Winsor & Newton_Cadmium Yellow', 1.0)
    print('빨강 + 노랑 = ' + result['result_hex'])

    print('\n[무채색 만들기]')
    neutralize_info = mixer.find_neutralizing_color('#FF6B9D')
    print('\n입력 색: ' + neutralize_info['input_hex'])
    print('CMY 값: C=' + str(neutralize_info['input_cmy']['c']) + ', ' + 'M=' + str(neutralize_info['input_cmy']['m']) + ', ' + 'Y=' + str(neutralize_info['input_cmy']['y']))
    print('\n이상적인 보색(무채색화색): ' + str(neutralize_info['ideal_complementary']))
    print('라이브러리에서 가장 가까운 물감: ' + str(neutralize_info['closest_paint_in_library']))


if __name__ == '__main__':
    demo()
