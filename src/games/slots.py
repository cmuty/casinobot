import secrets
import hmac
import hashlib


class SlotMachine:
    """Слот-машина с Provably Fair"""
    
    SYMBOLS = ['🍒', '🍋', '🍊', '🍉', '⭐', '7️⃣', '💎']
    WEIGHTS = [30, 25, 20, 15, 7, 2, 1]
    
    PAYTABLE = {
        '🍒🍒🍒': 2,
        '🍋🍋🍋': 3,
        '🍊🍊🍊': 5,
        '🍉🍉🍉': 10,
        '⭐⭐⭐': 20,
        '7️⃣7️⃣7️⃣': 50,
        '💎💎💎': 100,
    }
    
    @staticmethod
    def spin(server_seed: str, client_seed: str, nonce: int) -> list:
        """Генерация символов (Provably Fair)"""
        combined = f"{server_seed}:{client_seed}:{nonce}"
        hash_result = hmac.new(
            server_seed.encode(),
            combined.encode(),
            hashlib.sha256
        ).hexdigest()
        
        results = []
        for i in range(3):
            chunk = int(hash_result[i*16:(i+1)*16], 16)
            index = chunk % sum(SlotMachine.WEIGHTS)
            
            cumulative = 0
            for j, weight in enumerate(SlotMachine.WEIGHTS):
                cumulative += weight
                if index < cumulative:
                    results.append(SlotMachine.SYMBOLS[j])
                    break
        
        return results
    
    @staticmethod
    def calculate_payout(symbols: list, stake: int) -> int:
        """Расчёт выплаты"""
        key = ''.join(symbols)
        
        # Три одинаковых
        if len(set(symbols)) == 1:
            multiplier = SlotMachine.PAYTABLE.get(key, 0)
            return stake * multiplier
        
        # Два одинаковых
        if len(set(symbols)) == 2:
            return int(stake * 0.5)
        
        return 0