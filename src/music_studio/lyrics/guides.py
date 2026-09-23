from .compiler import HEADERS

CONTENT = {
    'intro': ('곡의 첫 분위기를 소개합니다. 짧은 시작이나 연주로 분위기를 만들 수 있습니다.', [4, 8]),
    'verse': ('이야기를 진행하고 새로운 정보나 감정을 전합니다. 장면의 변화를 시도할 수 있습니다.', [8, 16]),
    'pre_chorus': ('Chorus로 넘어가기 전 긴장감이나 에너지를 높일 수 있습니다.', [4, 8]),
    'chorus': ('핵심 메시지와 Hook을 담습니다. 기억하기 쉽게 가사나 멜로디를 반복할 수 있습니다.', [8, 16]),
    'post_chorus': ('Chorus 뒤에 짧은 Hook이나 여운을 이어갈 수 있습니다.', [4, 8]),
    'bridge': ('후반부에 다른 관점이나 분위기를 더할 수 있습니다.', [4, 8]),
    'breakdown': ('악기나 에너지를 덜어 대비를 만들 수 있습니다.', [4, 8]),
    'outro': ('반복 가사나 짧은 회상으로 마무리할 수 있습니다.', [4, 8]),
    'instrumental': ('연주를 의도한 구간입니다. 현재 빈 구간은 생성 텍스트에서 제외됩니다.', [4, 8]),
    'custom': ('직접 이름과 역할을 정합니다. 엔진에는 [Custom] 힌트를 보냅니다.', [4, 8, 16]),
}

def workshop():
    return {'types': [dict(type=k, label=HEADERS[k], description=v[0], options=[
        dict(bars=n, reason=f'{n}마디를 하나의 반복 또는 전개 단위로 시도할 수 있습니다. 규칙이 아니며 곡에 맞게 바꿔도 좋습니다.')
        for n in v[1]]) for k, v in CONTENT.items()],
        'notice': '행 수와 마디 수는 다릅니다. 마디 수와 구간 이름은 작곡 의도이며 실제 출력의 길이나 구조를 보장하지 않습니다.'}
