"""
PUBG 다중 모드 분석기
- 솔로/듀오/스쿼드 경쟁전 모두 분석
- 핵심 지표만 수집: 킬, 데미지, 어시스트, 순위, 생존시간, 레이팅
- 완전 랜덤 또는 유명 플레이어 시작점 선택 가능
"""

import requests
import time
import json
import csv
from datetime import datetime, timedelta, timezone

# ============================================
# 설정 구역
# ============================================

# API 키 입력
API_KEY = ""

# 분석 설정
SETTINGS = {
    'target_matches': 7,                    # 총 매치 수
    'platform': 'steam',                    # steam, xbox, psn
    'max_players_per_match': 100,           # 매치당 최대 플레이어 (Rate Limit 고려)
    'collection_method': 'known_players',   # 'random_samples', 'known_players', 'mixed'
    'game_modes': ['squad'],                # 분석할 게임 모드들
    'ranked_only': True,                    # 경쟁전만 분석
    'matches_per_mode': 1,                  # 새로 추가: 모드별 매치 수
    'balanced_collection': True,            # 새로 추가: 모드별 균등 수집
}

# 시작점용 플레이어들 (known_players 또는 mixed 방식용)
SEED_PLAYERS = [
    'KKyydsDDDD_'
]

def collect_matches(self):
    """설정에 따른 매치 수집"""
    print("\n1단계: 매치 수집")
    print("-" * 40)
    
    method = self.settings['collection_method']
    matches = []
    
    if method == 'random_samples':
        matches = self.get_random_samples()
    elif method == 'known_players':
        matches = self.get_matches_from_known_players()
    elif method == 'mixed':
        # 절반은 랜덤, 절반은 알려진 플레이어
        target_each = self.settings['target_matches'] // 2
        
        print("1부: 랜덤 샘플 수집")
        random_matches = self.get_random_samples()[:target_each]
        
        print("\n2부: 알려진 플레이어 매치 수집")
        known_matches = self.get_matches_from_known_players()[:target_each]
        
        matches = random_matches + known_matches
        matches = list(set(matches))  # 중복 제거
    
    if not matches:
        print("매치 수집 실패")
        print("다른 collection_method를 시도해보세요")
    
    return matches

class MultiModePubgAnalyzer:
    def __init__(self, api_key, settings):
        if api_key == "여기에_발급받은_API키_입력":
            print("API_KEY를 실제 발급받은 키로 변경해주세요!")
            exit(1)
            
        self.api_key = api_key
        self.settings = settings
        self.base_url = 'https://api.pubg.com'
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/vnd.api+json'
        }
        
        self.current_season_id = None
        self.request_count = 0
        self.start_time = time.time()
        
        print("PUBG 다중 모드 분석기 초기화 완료")
        print(f"목표: {settings['target_matches']}개 매치 분석")
        print(f"플랫폼: {settings['platform']}")
        print(f"게임 모드: {', '.join(settings['game_modes'])}")
        print(f"수집 방법: {settings['collection_method']}")
        print(f"경쟁전만: {settings['ranked_only']}")
    
    def wait_for_rate_limit(self):
        """Rate Limit 관리"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        if elapsed >= 60:
            self.request_count = 0
            self.start_time = current_time
            print("Rate limit 리셋")
        
        if self.request_count >= 10:
            wait_time = 60 - elapsed
            print(f"Rate limit 도달. {wait_time:.0f}초 대기 중...")
            time.sleep(wait_time)
            self.request_count = 0
            self.start_time = time.time()
        
        time.sleep(1)
    
    def make_api_request(self, url, description=""):
        """안전한 API 요청"""
        self.wait_for_rate_limit()
        
        self.request_count += 1
        print(f"API 요청 ({self.request_count}/10): {description}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 429:
                print("Rate limit 초과. 60초 대기...")
                time.sleep(60)
                return self.make_api_request(url, description)
            
            if response.status_code in [400, 404]:
                print(f"{response.status_code}: {description}")
                return None
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"API 요청 실패 ({description}): {e}")
            return None
    
    def get_current_season(self):
        """현재 시즌 찾기"""
        print("현재 시즌 확인 중...")
        
        url = f"{self.base_url}/shards/{self.settings['platform']}/seasons"
        data = self.make_api_request(url, "시즌 목록 조회")
        
        if not data:
            return None
        
        seasons = data.get('data', [])
        for season in seasons:
            if season.get('attributes', {}).get('isCurrentSeason', False):
                season_id = season['id']
                print(f"현재 시즌: {season_id}")
                return season_id
        
        if seasons:
            latest = seasons[-1]['id']
            print(f"최근 시즌 사용: {latest}")
            return latest
        
        return None
    
    def get_random_samples(self):
        """랜덤 샘플 매치 가져오기"""
        print("랜덤 샘플 매치 검색 중...")
        
        # 다양한 시간대의 샘플 시도
        time_offsets = [24, 48, 72]  # 24시간, 48시간, 72시간 전
        all_matches = []
        
        for hours_ago in time_offsets:
            if len(all_matches) >= self.settings['target_matches']:
                break
                
            past_time = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
            timestamp = past_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            url = f"{self.base_url}/shards/{self.settings['platform']}/samples?filter[createdAt-start]={timestamp}"
            data = self.make_api_request(url, f"{hours_ago}시간 전 샘플 조회")
            
            if data and 'data' in data:
                sample_data = data['data']
                print(f"   {hours_ago}시간 전: {len(sample_data)}개 샘플 발견")
                
                for match in sample_data:
                    if isinstance(match, dict) and 'id' in match:
                        all_matches.append(match['id'])
                        if len(all_matches) >= self.settings['target_matches']:
                            break
        
        print(f"총 {len(all_matches)}개의 랜덤 샘플 매치 수집")
        return all_matches
    
    def get_matches_from_known_players(self):
        """알려진 플레이어들로부터 매치 수집"""
        print("알려진 플레이어들로부터 매치 수집 중...")
        
        all_matches = set()
        
        for player_name in SEED_PLAYERS:
            if len(all_matches) >= self.settings['target_matches']:
                break
                
            print(f"플레이어 검색: {player_name}")
            
            # 플레이어 검색
            url = f"{self.base_url}/shards/{self.settings['platform']}/players?filter[playerNames]={player_name}"
            data = self.make_api_request(url, f"플레이어 {player_name} 검색")
            
            if data and 'data' in data and len(data['data']) > 0:
                player_id = data['data'][0]['id']
                
                # 플레이어의 매치 가져오기
                player_url = f"{self.base_url}/shards/{self.settings['platform']}/players/{player_id}"
                player_data = self.make_api_request(player_url, f"{player_name}의 매치 조회")
                
                if player_data and 'data' in player_data:
                    matches_data = player_data['data']['relationships']['matches']['data']
                    print(f"   {len(matches_data)}개 매치 발견")
                    
                    for match in matches_data[:16]:  # 각 플레이어당 최대
                        if isinstance(match, dict) and 'id' in match:
                            all_matches.add(match['id'])
                            if len(all_matches) >= self.settings['target_matches']:
                                break
                else:
                    print(f"   {player_name}의 매치 데이터 없음")
            else:
                print(f"   플레이어 {player_name} 찾기 실패")
        
        match_list = list(all_matches)[:self.settings['target_matches']]
        print(f"총 {len(match_list)}개의 매치 수집")
        return match_list
    
    def evaluate_match_quality(self, match_id):
        """매치 품질 평가 (레이팅 보유자 비율 확인)"""
        # 매치 기본 정보 가져오기
        url = f"{self.base_url}/shards/{self.settings['platform']}/matches/{match_id}"
        data = self.make_api_request(url, f"매치 {match_id[:15]}... 품질 평가")
        
        if not data:
            return None
        
        # 게임 모드와 타입 확인
        mode, is_ranked = self.analyze_match_mode_and_type(data)
        
        # 필터링 조건 확인
        if mode not in self.settings['game_modes']:
            return None
        
        if self.settings['ranked_only'] and not is_ranked:
            return None
        
        # 참가자 추출
        participants = []
        included_data = data.get('included', [])
        
        for item in included_data:
            if isinstance(item, dict) and item.get('type') == 'participant':
                attributes = item.get('attributes', {})
                stats = attributes.get('stats', {})
                participants.append({
                    'player_id': stats.get('playerId', ''),
                    'player_name': stats.get('name', 'Unknown')
                })
        
        if len(participants) == 0:
            return None
        
        # 샘플링으로 레이팅 보유율 확인 (처음 10명만)
        sample_size = min(10, len(participants))
        sample_participants = participants[:sample_size]
        
        rated_count = 0
        for participant in sample_participants:
            current_rp, _ = self.get_player_rating_for_mode(
                participant['player_id'], 
                participant['player_name'], 
                mode
            )
            if current_rp > 0:
                rated_count += 1
        
        # 매치 품질 점수 계산
        rating_coverage = rated_count / sample_size
        quality_score = rating_coverage * 100
        
        return {
            'match_id': match_id,
            'game_mode': mode,
            'is_ranked': is_ranked,
            'total_participants': len(participants),
            'sample_size': sample_size,
            'rated_in_sample': rated_count,
            'rating_coverage': rating_coverage,
            'quality_score': quality_score
        }
    
    def select_best_matches(self, candidate_matches):
        """후보 매치들 중에서 레이팅 보유율이 높은 매치들 선택"""
        print(f"{len(candidate_matches)}개 후보 매치의 품질 평가 중...")
        
        match_qualities = []
        
        for i, match_id in enumerate(candidate_matches):
            print(f"   매치 {i+1}/{len(candidate_matches)}: {match_id[:15]}... 평가 중")
            
            quality = self.evaluate_match_quality(match_id)
            if quality:
                match_qualities.append(quality)
                print(f"      {quality['game_mode']} {'경쟁전' if quality['is_ranked'] else '일반'}: "
                      f"{quality['rated_in_sample']}/{quality['sample_size']} 레이팅 보유 "
                      f"({quality['quality_score']:.1f}%)")
            else:
                print(f"      분석 조건에 부합하지 않음")
        
        if not match_qualities:
            print("품질 평가를 통과한 매치가 없습니다.")
            return []
        
        # 품질 점수 순으로 정렬
        match_qualities.sort(key=lambda x: x['quality_score'], reverse=True)
        
        # 상위 매치들 선택
        target_count = self.settings['target_matches']
        selected_matches = match_qualities[:target_count]
        
        print(f"\n품질 기준으로 선택된 매치들:")
        for i, match in enumerate(selected_matches, 1):
            print(f"   {i}. {match['match_id'][:15]}... "
                  f"({match['game_mode']}, 레이팅 보유율: {match['quality_score']:.1f}%)")
        
        return [match['match_id'] for match in selected_matches]
    
    def collect_matches(self):
        """설정에 따른 매치 수집"""
        print("\n1단계: 매치 수집")
        print("-" * 40)
        
        method = self.settings['collection_method']
        matches = []
        
        if method == 'random_samples':
            matches = self.get_random_samples()
        elif method == 'known_players':
            matches = self.get_matches_from_known_players()
        elif method == 'mixed':
            # 절반은 랜덤, 절반은 알려진 플레이어
            target_each = self.settings['target_matches'] // 2
            
            print("1부: 랜덤 샘플 수집")
            random_matches = self.get_random_samples()[:target_each]
            
            print("\n2부: 알려진 플레이어 매치 수집")
            known_matches = self.get_matches_from_known_players()[:target_each]
            
            matches = random_matches + known_matches
            matches = list(set(matches))  # 중복 제거
        
        if not matches:
            print("매치 수집 실패")
            print("다른 collection_method를 시도해보세요")
        
        return matches
    
    def analyze_match_mode_and_type(self, match_data):
        """매치의 게임 모드와 타입 분석"""
        if not match_data:
            return None, None
        
        match_attributes = match_data.get('data', {}).get('attributes', {})
        game_mode = match_attributes.get('gameMode', '')
        is_custom = match_attributes.get('isCustomMatch', False)
        
        # 게임 모드 판별
        mode = None
        if 'solo' in game_mode.lower():
            mode = 'solo'
        elif 'duo' in game_mode.lower():
            mode = 'duo'
        elif 'squad' in game_mode.lower():
            mode = 'squad'
        
        # 경쟁전 여부 판별
        is_ranked = False
        if not is_custom and mode:
            # 참가자 수로 판별 (경쟁전은 보통 특정 인원수)
            participants = [item for item in match_data.get('included', []) 
                          if item.get('type') == 'participant']
            participant_count = len(participants)
            
            # 경쟁전 인원수 기준 (대략적)
            if ((mode == 'solo' and participant_count >= 60) or
                (mode == 'duo' and participant_count >= 60) or
                (mode == 'squad' and participant_count >= 60)):
                is_ranked = True
        
        return mode, is_ranked
    
    def get_core_match_data(self, match_id):
        """매치의 핵심 데이터만 추출"""
        url = f"{self.base_url}/shards/{self.settings['platform']}/matches/{match_id}"
        data = self.make_api_request(url, f"매치 {match_id[:15]}... 분석")
        
        if not data:
            return None
        
        # 게임 모드와 타입 확인
        mode, is_ranked = self.analyze_match_mode_and_type(data)
        
        # 필터링 조건 확인
        if mode not in self.settings['game_modes']:
            print(f"   게임 모드 {mode}는 분석 대상이 아님")
            return None
        
        if self.settings['ranked_only'] and not is_ranked:
            print(f"   일반 매치는 스킵 (경쟁전만 분석)")
            return None
        
        # 참가자 데이터 추출
        participants = []
        included_data = data.get('included', [])
        
        for item in included_data:
            if isinstance(item, dict) and item.get('type') == 'participant':
                attributes = item.get('attributes', {})
                stats = attributes.get('stats', {})
                
                # 핵심 데이터만 추출
                participants.append({
                    'player_id': stats.get('playerId', ''),
                    'player_name': stats.get('name', 'Unknown'),
                    'kills': stats.get('kills', 0),
                    'damage': round(stats.get('damageDealt', 0), 1),
                    'assists': stats.get('assists', 0),
                    'win_place': stats.get('winPlace', 0),
                    'time_survived': round(stats.get('timeSurvived', 0), 1),
                })
        
        print(f"   {mode} {'경쟁전' if is_ranked else '일반'} 매치: {len(participants)}명")
        
        # 플레이어 수 제한
        max_players = self.settings['max_players_per_match']
        if len(participants) > max_players:
            print(f"   플레이어 수 제한으로 상위 {max_players}명만 분석")
            participants = participants[:max_players]
        
        return {
            'match_id': match_id,
            'game_mode': mode,
            'is_ranked': is_ranked,
            'participants': participants
        }
    
    def get_player_rating_for_mode(self, player_id, player_name, game_mode):
        """게임 모드별 플레이어 레이팅 조회 (핵심 정보만)"""
        if not self.current_season_id:
            return 0, 0
        
        url = f"{self.base_url}/shards/{self.settings['platform']}/players/{player_id}/seasons/{self.current_season_id}/ranked"
        data = self.make_api_request(url, f"{player_name[:10]}... {game_mode} RP")
        
        if not data:
            return 0, 0
        
        try:
            player_data = data.get('data', {})
            attributes = player_data.get('attributes', {})
            ranked_stats = attributes.get('rankedGameModeStats', {})
            
            # 게임 모드별 통계 선택
            mode_stats = None
            if game_mode == 'solo':
                mode_stats = ranked_stats.get('solo', {})
            elif game_mode == 'duo':
                mode_stats = ranked_stats.get('duo', {})
            elif game_mode == 'squad':
                mode_stats = ranked_stats.get('squad', {})
            
            if mode_stats:
                current_rp = mode_stats.get('currentRankPoint', 0)
                best_rp = mode_stats.get('bestRankPoint', 0)
                return current_rp, best_rp
            else:
                return 0, 0
                
        except Exception as e:
            print(f"   {player_name} 레이팅 파싱 실패: {e}")
            return 0, 0
    
    def analyze_match_with_ratings(self, match_info, match_number, total_matches):
        """매치 분석 + 레이팅 정보 추가 (원래 버전)"""
        print(f"\n매치 {match_number}/{total_matches}: {match_info['match_id'][:15]}...")
        print(f"   모드: {match_info['game_mode']} {'(경쟁전)' if match_info['is_ranked'] else '(일반)'}")
        
        participants = match_info['participants']
        game_mode = match_info['game_mode']
        
        # 각 참가자의 레이팅 정보 추가
        complete_data = []
        rated_count = 0
        
        for i, participant in enumerate(participants):
            # 진행 상황 표시 (10명마다)
            if i % 10 == 0:
                print(f"   레이팅 조회 중: {i+1}/{len(participants)}")
            
            # 핵심 레이팅 정보만 조회
            current_rp, best_rp = self.get_player_rating_for_mode(
                participant['player_id'], 
                participant['player_name'], 
                game_mode
            )
            
            if current_rp > 0:
                rated_count += 1
            
            # 완전한 데이터 구성 (모든 플레이어 포함)
            complete_data.append({
                'match_id': match_info['match_id'],
                'match_number': match_number,
                'game_mode': game_mode,
                'is_ranked': match_info['is_ranked'],
                **participant,  # kills, damage, assists, win_place, time_survived
                'current_rp': current_rp,
                'best_rp': best_rp,
                'analyzed_at': datetime.now().isoformat()
            })
        
        rating_coverage = (rated_count / len(participants)) * 100
        print(f"   매치 {match_number} 완료: {len(participants)}명, 레이팅 보유 {rated_count}명 ({rating_coverage:.1f}%)")
        
        return complete_data
    
    def run_analysis(self):
        """전체 분석 실행"""
        print("PUBG 다중 모드 분석 시작!")
        print("=" * 60)
        
        start_time = time.time()
        
        try:
            # 0단계: 시즌 확인
            print("0단계: 현재 시즌 확인")
            print("-" * 40)
            self.current_season_id = self.get_current_season()
            
            # 1단계: 매치 수집
            match_ids = self.collect_matches()
            if not match_ids:
                return None
            
            # 2단계: 매치 필터링 및 기본 정보 수집
            print(f"\n2단계: 매치 타입 확인 및 필터링")
            print("-" * 40)
            
            valid_matches = []
            for i, match_id in enumerate(match_ids, 1):
                print(f"매치 {i}/{len(match_ids)}: {match_id[:15]}... 확인 중")
                
                match_info = self.get_core_match_data(match_id)
                if match_info:
                    valid_matches.append(match_info)
            
            if not valid_matches:
                print("분석 가능한 매치가 없습니다.")
                return None
            
            print(f"\n필터링 결과: {len(valid_matches)}개 매치가 분석 조건에 부합")
            
            # 게임 모드별 분포 표시
            mode_count = {}
            for match in valid_matches:
                mode = match['game_mode']
                ranked = match['is_ranked']
                key = f"{mode} {'경쟁전' if ranked else '일반'}"
                mode_count[key] = mode_count.get(key, 0) + 1
            
            print("매치 분포:")
            for mode, count in mode_count.items():
                print(f"   - {mode}: {count}개")
            
            # 3단계: 레이팅 포함 상세 분석
            print(f"\n3단계: {len(valid_matches)}개 매치 상세 분석")
            print("-" * 40)
            
            all_data = []
            
            for i, match_info in enumerate(valid_matches, 1):
                match_data = self.analyze_match_with_ratings(match_info, i, len(valid_matches))
                all_data.extend(match_data)
                
                progress = (i / len(valid_matches)) * 100
                print(f"전체 진행률: {progress:.1f}% ({i}/{len(valid_matches)} 매치 완료)")
            
            # 4단계: 결과 정리
            print(f"\n4단계: 결과 정리")
            print("-" * 40)
            
            if all_data:
                results = self.process_results(all_data)
                self.save_results(results)
                self.print_summary(results)
                
                elapsed_time = time.time() - start_time
                print(f"\n다중 모드 분석 완료! (소요 시간: {elapsed_time/60:.1f}분)")
                
                return results
            else:
                print("수집된 데이터가 없습니다.")
                return None
                
        except KeyboardInterrupt:
            print("\n사용자에 의해 중단되었습니다.")
            return None
        except Exception as e:
            print(f"\n예상치 못한 오류: {e}")
            return None
    
    def process_results(self, all_data):
        """결과 데이터 처리"""
        print(f"{len(all_data)}개의 플레이어 데이터 처리 중...")
        
        # 매치별로 그룹화
        matches = {}
        for data in all_data:
            match_id = data['match_id']
            if match_id not in matches:
                matches[match_id] = []
            matches[match_id].append(data)
        
        # 통계 계산
        total_players = len(all_data)
        unique_players = len(set(data['player_id'] for data in all_data))
        rated_players = len([d for d in all_data if d['current_rp'] > 0])
        
        # 게임 모드별 통계
        mode_stats = {}
        for mode in self.settings['game_modes']:
            mode_data = [d for d in all_data if d['game_mode'] == mode]
            mode_rated = [d for d in mode_data if d['current_rp'] > 0]
            
            mode_stats[mode] = {
                'total_players': len(mode_data),
                'rated_players': len(mode_rated),
                'avg_current_rp': sum(d['current_rp'] for d in mode_rated) / len(mode_rated) if mode_rated else 0,
                'avg_best_rp': sum(d['best_rp'] for d in mode_rated) / len(mode_rated) if mode_rated else 0,
                'avg_kills': sum(d['kills'] for d in mode_data) / len(mode_data) if mode_data else 0,
                'avg_damage': sum(d['damage'] for d in mode_data) / len(mode_data) if mode_data else 0
            }
        
        # 레이팅 정보가 있는 플레이어들만
        rated_data = [d for d in all_data if d['current_rp'] > 0]
        
        return {
            'matches': matches,
            'all_players': all_data,
            'mode_statistics': mode_stats,
            'statistics': {
                'total_matches': len(matches),
                'total_players': total_players,
                'unique_players': unique_players,
                'rated_players': rated_players,
                'rating_coverage': (rated_players / total_players * 100) if total_players > 0 else 0,
                'avg_current_rp': sum(d['current_rp'] for d in rated_data) / len(rated_data) if rated_data else 0,
                'avg_best_rp': sum(d['best_rp'] for d in rated_data) / len(rated_data) if rated_data else 0,
                'max_current_rp': max((d['current_rp'] for d in rated_data), default=0),
                'min_current_rp': min((d['current_rp'] for d in rated_data if d['current_rp'] > 0), default=0),
                'current_season': self.current_season_id,
                'analyzed_modes': self.settings['game_modes']
            }
        }
    
    def save_results(self, results):
        """결과 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON 저장
        json_filename = f"pubg_multimode_analysis_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        print(f"JSON 저장: {json_filename}")
        
        # CSV 저장
        csv_filename = f"pubg_multimode_analysis_{timestamp}.csv"
        if results['all_players']:
            fieldnames = results['all_players'][0].keys()
            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results['all_players'])
            print(f"CSV 저장: {csv_filename}")
    
    def print_summary(self, results):
        """결과 요약 출력"""
        stats = results['statistics']
        mode_stats = results['mode_statistics']
        
        print(f"\n다중 모드 분석 결과")
        print("=" * 50)
        print(f"시즌: {stats['current_season']}")
        print(f"분석 모드: {', '.join(stats['analyzed_modes'])}")
        print(f"총 매치: {stats['total_matches']}개")
        print(f"총 플레이어: {stats['total_players']:,}명")
        print(f"고유 플레이어: {stats['unique_players']:,}명")
        print(f"레이팅 보유: {stats['rated_players']:,}명 ({stats['rating_coverage']:.1f}%)")
        
        if stats['avg_current_rp'] > 0:
            print(f"\n전체 레이팅 통계")
            print("-" * 30)
            print(f"평균 현재 RP: {stats['avg_current_rp']:.0f}")
            print(f"평균 최고 RP: {stats['avg_best_rp']:.0f}")
            print(f"최고 현재 RP: {stats['max_current_rp']:,}")
            print(f"최저 현재 RP: {stats['min_current_rp']:,}")
        
        # 게임 모드별 통계
        print(f"\n게임 모드별 통계")
        print("-" * 30)
        for mode, mode_stat in mode_stats.items():
            if mode_stat['total_players'] > 0:
                print(f"\n{mode.upper()}:")
                print(f"  플레이어: {mode_stat['total_players']}명")
                print(f"  레이팅 보유: {mode_stat['rated_players']}명")
                if mode_stat['avg_current_rp'] > 0:
                    print(f"  평균 현재 RP: {mode_stat['avg_current_rp']:.0f}")
                    print(f"  평균 최고 RP: {mode_stat['avg_best_rp']:.0f}")
                print(f"  평균 킬: {mode_stat['avg_kills']:.1f}")
                print(f"  평균 데미지: {mode_stat['avg_damage']:.0f}")
        
        # RP 분포 (간단화)
        print(f"\nRP 분포")
        print("-" * 30)
        
        # RP 범위별 분포 계산
        rp_ranges = [
            (0, 0, 'Unranked'),
            (1, 1499, 'Bronze-Silver'),
            (1500, 2499, 'Gold'),
            (2500, 3499, 'Platinum'),
            (3500, 4499, 'Diamond'),
            (4500, 9999, 'Master+')
        ]
        
        for min_rp, max_rp, range_name in rp_ranges:
            if min_rp == 0 and max_rp == 0:
                # Unranked (RP = 0)
                count = len([p for p in results['all_players'] if p['current_rp'] == 0])
            else:
                # 범위별 계산
                count = len([p for p in results['all_players'] 
                           if min_rp <= p['current_rp'] <= max_rp])
            
            if count > 0:
                percentage = (count / stats['total_players']) * 100
                print(f"{range_name}: {count}명 ({percentage:.1f}%)")

def main():
    print("PUBG 다중 모드 분석기 (솔로/듀오/스쿼드)")
    print("=" * 60)
    print("현재 설정:")
    for key, value in SETTINGS.items():
        print(f"   {key}: {value}")
    print()
    print("이 버전의 특징:")
    print("   - 솔로/듀오/스쿼드 경쟁전 모두 분석")
    print("   - 핵심 지표만 수집 (킬, 데미지, 어시스트, 순위, 생존시간, 레이팅)")
    print("   - 게임 모드별 레이팅 시스템 지원")
    print("   - 랜덤 + 알려진 플레이어 혼합 방식")
    if SETTINGS.get('filter_unranked', False):
        print("   - 레이팅 없는 플레이어 자동 제외")
    if SETTINGS.get('min_rating_filter', 0) > 0:
        print(f"   - {SETTINGS['min_rating_filter']} RP 미만 플레이어 제외")
    print()
    
    analyzer = MultiModePubgAnalyzer(API_KEY, SETTINGS)
    results = analyzer.run_analysis()
    
    if results:
        print(f"\n주요 결과:")
        print(f"   - 분석 매치: {results['statistics']['total_matches']}개")
        print(f"   - 총 플레이어: {results['statistics']['total_players']:,}명")
        print(f"   - 레이팅 보유자: {results['statistics']['rated_players']:,}명")
        print(f"   - 레이팅 보유율: {results['statistics']['rating_coverage']:.1f}%")
        print(f"   - 분석 모드: {', '.join(results['statistics']['analyzed_modes'])}")
        print(f"\n핵심 데이터:")
        print(f"   - 킬, 데미지, 어시스트, 순위, 생존시간")
        print(f"   - 게임 모드별 레이팅 정보")
        print(f"   - 솔로/듀오/스쿼드 통계 비교 가능")
    else:
        print(f"\n다중 모드 분석에 실패했습니다.")
        print(f"해결 방법:")
        print(f"   1. collection_method 변경: 'random_samples', 'known_players', 'mixed'")
        print(f"   2. target_matches 줄이기 (현재: {SETTINGS['target_matches']})")
        print(f"   3. ranked_only를 False로 변경 (일반 매치도 포함)")
        print(f"   4. game_modes에서 일부 모드 제외")

if __name__ == "__main__":
    main()