from dataclasses import dataclass, field
from typing import Dict, Callable, Optional, List, Tuple
import time

# ---------- Modelo de inventário ----------
class Inventory:
    def __init__(self):
        self.items: Dict[str, float] = {}

    def add(self, item: str, amount: float):
        self.items[item] = self.items.get(item, 0.0) + amount

    def has(self, req: Dict[str, float]) -> bool:
        return all(self.items.get(k, 0.0) >= v for k, v in req.items())

    def remove(self, req: Dict[str, float]) -> bool:
        if not self.has(req):
            return False
        for k, v in req.items():
            self.items[k] -= v
        return True

    def snapshot(self) -> Dict[str, float]:
        # arredonda só para exibição
        return {k: round(v, 2) for k, v in sorted(self.items.items()) if v > 0.0001}


# ---------- Receitas / Processos ----------
@dataclass
class Recipe:
    id: str
    name: str
    time_s: float
    inputs: Dict[str, float]
    outputs: Dict[str, float]
    requires: Dict[str, float] = field(default_factory=dict)   # ex: {"serra":1}
    unlock_condition: Optional[Callable[['Game'], bool]] = None # gating opcional

    def is_unlocked(self, game: 'Game') -> bool:
        if self.unlock_condition is None:
            return True
        return self.unlock_condition(game)


# ---------- Job em execução ----------
@dataclass
class Job:
    recipe_id: str
    remaining: float


# ---------- Jogo ----------
class Game:
    def __init__(self):
        self.inv = Inventory()

        # "estações/ferramentas" são itens também (serra, forja, etc.)
        self.inv.add("mãos", 1)  # sempre existe

        self.recipes: Dict[str, Recipe] = {}
        self.queue: List[Job] = []

        # exemplo de progressão / tecnologia
        self.tech: Dict[str, bool] = {
            "serraria": False,
            "carpintaria": False,
        }

        self._init_recipes()

    def _init_recipes(self):
        # cortar árvore: usa mãos, gera lenha
        self.add_recipe(Recipe(
            id="cut_tree",
            name="Cortar árvore",
            time_s=2.0,
            inputs={},
            outputs={"lenha": 3},
            requires={"mãos": 1},
        ))

        # construir serra (desbloqueia serraria) — feito com lenha
        self.add_recipe(Recipe(
            id="build_saw",
            name="Construir serra (desbloqueia Serraria)",
            time_s=5.0,
            inputs={"lenha": 12},
            outputs={"serra": 1},
            requires={"mãos": 1},
            unlock_condition=lambda g: not g.tech["serraria"]
        ))

        # serrar lenha -> tábuas (requer serra)
        self.add_recipe(Recipe(
            id="saw_planks",
            name="Serrar lenha em tábuas",
            time_s=3.0,
            inputs={"lenha": 4},
            outputs={"tábuas": 2},
            requires={"serra": 1},
            unlock_condition=lambda g: g.tech["serraria"]
        ))

        # construir bancada de carpintaria (desbloqueia carpintaria)
        self.add_recipe(Recipe(
            id="build_workbench",
            name="Construir bancada de carpintaria",
            time_s=8.0,
            inputs={"tábuas": 10},
            outputs={"bancada": 1},
            requires={"serra": 1},
            unlock_condition=lambda g: g.tech["serraria"] and not g.tech["carpintaria"]
        ))

        # fabricar caixa com tábuas (requer bancada)
        self.add_recipe(Recipe(
            id="make_crate",
            name="Fazer caixa de madeira",
            time_s=4.0,
            inputs={"tábuas": 6},
            outputs={"caixa": 1},
            requires={"bancada": 1},
            unlock_condition=lambda g: g.tech["carpintaria"]
        ))

    def add_recipe(self, r: Recipe):
        self.recipes[r.id] = r

    def unlocked_recipes(self) -> List[Recipe]:
        return [r for r in self.recipes.values() if r.is_unlocked(self)]

    def can_start(self, recipe: Recipe) -> Tuple[bool, str]:
        if not recipe.is_unlocked(self):
            return False, "Receita bloqueada"
        if not self.inv.has(recipe.requires):
            return False, f"Falta requisito: {recipe.requires}"
        if not self.inv.has(recipe.inputs):
            return False, f"Faltam recursos: {recipe.inputs}"
        return True, "OK"

    def start_job(self, recipe_id: str, qty: int = 1) -> bool:
        if recipe_id not in self.recipes:
            return False
        recipe = self.recipes[recipe_id]

        for _ in range(qty):
            ok, _ = self.can_start(recipe)
            if not ok:
                return False
            # consome inputs ao iniciar (idle “de verdade”)
            self.inv.remove(recipe.inputs)
            self.queue.append(Job(recipe_id=recipe.id, remaining=recipe.time_s))
        return True

    def _on_recipe_complete(self, recipe: Recipe):
        # entrega outputs
        for k, v in recipe.outputs.items():
            self.inv.add(k, v)

        # atualiza tech conforme itens especiais
        if recipe.id == "build_saw":
            self.tech["serraria"] = True
        if recipe.id == "build_workbench":
            self.tech["carpintaria"] = True

    def tick(self, dt: float):
        if not self.queue:
            return
        # processa só 1 job por vez (fila única). Você pode evoluir para múltiplos workers.
        job = self.queue[0]
        job.remaining -= dt
        if job.remaining <= 0:
            recipe = self.recipes[job.recipe_id]
            self._on_recipe_complete(recipe)
            self.queue.pop(0)

    def status(self) -> str:
        q = ""
        if self.queue:
            r = self.recipes[self.queue[0].recipe_id]
            q = f" | Fazendo: {r.name} ({self.queue[0].remaining:.1f}s)"
        return f"Inventário: {self.inv.snapshot()} | Tech: {self.tech}{q}"


# ---------- Loop simples de terminal ----------
def main():
    g = Game()
    last = time.time()

    print("Idle (terminal). Comandos: list | do <id> [qtd] | status | help | quit")
    print("Dica: comece com 'do cut_tree 3', depois 'do build_saw 1'.")

    while True:
        now = time.time()
        dt = now - last
        last = now
        g.tick(dt)

        # input não-bloqueante “de verdade” é mais chato; aqui vamos pedir comando sempre.
        cmd = input("\n> ").strip().split()
        if not cmd:
            print(g.status())
            continue

        if cmd[0] in ("quit", "exit"):
            break

        if cmd[0] == "status":
            print(g.status())
            continue

        if cmd[0] == "list":
            for r in g.unlocked_recipes():
                ok, reason = g.can_start(r)
                tag = "OK" if ok else f"NO ({reason})"
                print(f"- {r.id}: {r.name} | t={r.time_s}s | in={r.inputs} | out={r.outputs} | req={r.requires} => {tag}")
            continue

        if cmd[0] == "do" and len(cmd) >= 2:
            rid = cmd[1]
            qty = int(cmd[2]) if len(cmd) >= 3 else 1
            if g.start_job(rid, qty):
                print("Adicionado à fila.")
            else:
                print("Não foi possível iniciar (faltam recursos/requisitos ou está bloqueado).")
            print(g.status())
            continue

        if cmd[0] == "help":
            print("list: mostra receitas desbloqueadas")
            print("do <id> [qtd]: coloca na fila")
            print("status: estado atual")
            print("quit: sair")
            continue

        print("Comando desconhecido. Use help.")

if __name__ == "__main__":
    main()