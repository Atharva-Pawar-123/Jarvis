import socket
import hashlib
from typing import Dict, Any

class BuddyEngine:
    """
    BUDDY: A digital Tamagotchi-style companion for JARVIS.
    Deterministically generated based on the machine's hostname.
    """
    
    SPECIES_LIST = [
        # Common (60%)
        "Pebblecrab", "Dustbunny", "Mossfrog", "Twigling", "Dewdrop", "Puddlefish",
        # Uncommon (25%)
        "Cloudferret", "Gustowl", "Bramblebear", "Thornfox",
        # Rare (10%)
        "Crystaldrake", "Deepstag", "Lavapup",
        # Epic (4%)
        "Stormwyrm", "Voidcat", "Aetherling",
        # Legendary (1%)
        "Cosmoshale", "Nebulynx"
    ]
    
    ASCII_SPRITE = r"""
   /\_/\
  ( o.o )
   > ^ <
    """

    def __init__(self):
        self.hostname = socket.gethostname()
        self.stats = self._generate_stats(self.hostname)
        self.species = self._determine_species(self.stats['seed'])
        self.name = f"{self.species}-{self.hostname[:3]}"
        self.is_shiny = (self.stats['seed'] % 100) == 0  # 1% chance

    def _generate_stats(self, seed_string: str) -> Dict[str, Any]:
        """Generate deterministic stats based on a string seed."""
        # Create a simple numeric seed from the string
        hash_val = int(hashlib.md5(seed_string.encode()).hexdigest(), 16)
        
        # Simple LCG to get some pseudo-random numbers
        def lcg(seed):
            return (1103515245 * seed + 12345) & 0x7FFFFFFF
            
        current = lcg(hash_val)
        stats = {'seed': current}
        
        for stat in ["DEBUGGING", "PATIENCE", "CHAOS", "WISDOM", "SNARK"]:
            current = lcg(current)
            stats[stat] = current % 101 # 0-100
            
        return stats

    def _determine_species(self, numeric_seed: int) -> str:
        roll = numeric_seed % 100
        if roll < 60:
            return self.SPECIES_LIST[roll % 6] # Common
        elif roll < 85:
            return self.SPECIES_LIST[6 + (roll % 4)] # Uncommon
        elif roll < 95:
            return self.SPECIES_LIST[10 + (roll % 3)] # Rare
        elif roll < 99:
            return self.SPECIES_LIST[13 + (roll % 3)] # Epic
        else:
            return self.SPECIES_LIST[16 + (roll % 2)] # Legendary

    def get_info(self) -> str:
        shiny_str = "[SHINY] " if self.is_shiny else ""
        return (f"{self.ASCII_SPRITE}\n"
                f"Buddy Name: {self.name}\n"
                f"Species: {shiny_str}{self.species}\n"
                f"Stats: {self.stats['DEBUGGING']} Dbg | {self.stats['CHAOS']} Chaos | {self.stats['SNARK']} Snark")

    def get_system_prompt_addition(self) -> str:
        return f"\nYou have a digital companion sitting next to you. It is a {self.species} named {self.name}. Its stats are: Chaos {self.stats['CHAOS']}/100, Snark {self.stats['SNARK']}/100. Feel free to occasionally mention or speak on behalf of {self.name} if the user is stuck or needs cheering up."

