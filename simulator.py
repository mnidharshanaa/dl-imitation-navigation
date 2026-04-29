import pygame
import math
import numpy as np

# Constants
WIDTH, HEIGHT = 800, 600
CAR_WIDTH, CAR_HEIGHT = 40, 20
FPS = 60
MAX_SENSOR_DIST = 300
STRICT_SPEED = 3  # Fixed speed as per hardware constraint
TURN_SPEED = 4

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
GRAY = (200, 200, 200)

class Car:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.angle = 0
        self.speed = 0
        self.sensors = [0, 0, 0] # Left, Front, Right
        self.rect = pygame.Rect(x, y, CAR_WIDTH, CAR_HEIGHT)
        self.collision = False

    def update(self, action):
        """
        Actions:
        0: STOP
        1: FORWARD
        2: LEFT
        3: RIGHT
        4: FORWARD_LEFT
        5: FORWARD_RIGHT
        """
        if action == 1: # FORWARD
            self.speed = STRICT_SPEED
        elif action == 2: # LEFT
            self.angle += TURN_SPEED
            self.speed = 0
        elif action == 3: # RIGHT
            self.angle -= TURN_SPEED
            self.speed = 0
        elif action == 4: # FORWARD_LEFT
            self.angle += TURN_SPEED
            self.speed = STRICT_SPEED
        elif action == 5: # FORWARD_RIGHT
            self.angle -= TURN_SPEED
            self.speed = STRICT_SPEED
        elif action == 6: # REVERSE
            self.speed = -STRICT_SPEED
        else: # STOP
            self.speed = 0

        # Movement
        self.x += self.speed * math.cos(math.radians(self.angle))
        self.y -= self.speed * math.sin(math.radians(self.angle))
        
        # Update rect for collision
        self.rect.center = (self.x, self.y)

    def cast_ray(self, angle_offset, walls):
        ray_angle = math.radians(self.angle + angle_offset)
        for d in range(0, MAX_SENSOR_DIST, 5):
            target_x = self.x + d * math.cos(ray_angle)
            target_y = self.y - d * math.sin(ray_angle)
            
            # Check screen boundaries
            if target_x < 0 or target_x > WIDTH or target_y < 0 or target_y > HEIGHT:
                return d / MAX_SENSOR_DIST
            
            # Check collisions with walls
            for wall in walls:
                if wall.collidepoint(target_x, target_y):
                    return d / MAX_SENSOR_DIST
        return 1.0

    def get_sensors(self, walls):
        # 45 deg left, 0 deg front, 45 deg right
        self.sensors[0] = self.cast_ray(45, walls)
        self.sensors[1] = self.cast_ray(0, walls)
        self.sensors[2] = self.cast_ray(-45, walls)
        return self.sensors

    def draw(self, screen):
        # Rotate car surface
        surf = pygame.Surface((CAR_WIDTH, CAR_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(surf, RED if self.collision else BLUE, (0, 0, CAR_WIDTH, CAR_HEIGHT))
        
        # Add a "front" indicator
        pygame.draw.rect(surf, BLACK, (CAR_WIDTH - 10, 5, 10, 10))
        
        rotated_surf = pygame.transform.rotate(surf, self.angle)
        new_rect = rotated_surf.get_rect(center=(self.x, self.y))
        screen.blit(rotated_surf, new_rect.topleft)

        # Draw sensors (rays)
        ray_angles = [45, 0, -45]
        for i, angle_off in enumerate(ray_angles):
            dist = self.sensors[i] * MAX_SENSOR_DIST
            ray_angle = math.radians(self.angle + angle_off)
            end_x = self.x + dist * math.cos(ray_angle)
            end_y = self.y - dist * math.sin(ray_angle)
            pygame.draw.line(screen, GREEN, (self.x, self.y), (end_x, end_y), 1)

def get_default_walls():
    return [
        pygame.Rect(0, 0, WIDTH, 20),
        pygame.Rect(0, HEIGHT-20, WIDTH, 20),
        pygame.Rect(0, 0, 20, HEIGHT),
        pygame.Rect(WIDTH-20, 0, 20, HEIGHT),
        # Track Layout (Complex)
        pygame.Rect(150, 100, 50, 250),
        pygame.Rect(300, 250, 200, 50),
        pygame.Rect(600, 100, 50, 300),
        pygame.Rect(150, 450, 400, 50),
        pygame.Rect(400, 50, 50, 100)
    ]

def run_simulation(on_frame=None):
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Autonomous Car Simulator")
    clock = pygame.time.Clock()
    
    car = Car(100, 100) # Move start to top-left to avoid center walls
    walls = get_default_walls()

    running = True
    while running:
        action = 0 
        keys = pygame.key.get_pressed()
        
        if keys[pygame.K_w]:
            action = 1 # FORWARD
        elif keys[pygame.K_s]:
            action = 6 # REVERSE
        elif keys[pygame.K_a]:
            action = 2 # LEFT
        elif keys[pygame.K_d]:
            action = 3 # RIGHT
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if on_frame:
                on_frame(event, car, action, "EVENT")

        # Callback for TICK (allows action override)
        is_rec = False
        is_auto = False
        if on_frame:
            res = on_frame(None, car, action, "TICK")
            if isinstance(res, dict):
                if "override_action" in res:
                    action = res["override_action"]
                is_rec = res.get("recording", False)
                is_auto = res.get("auto", False)

        # Physics Logic (with collision blocking)
        old_pos = (car.x, car.y)
        car.update(action)
        
        # Immediate collision check after move
        car.collision = False
        for wall in walls:
            if car.rect.colliderect(wall):
                car.collision = True
                car.x, car.y = old_pos # Backtrack
                car.rect.center = old_pos
                break
        
        sensors = car.get_sensors(walls)

        # Draw
        screen.fill(WHITE)
        for wall in walls:
            pygame.draw.rect(screen, GRAY, wall)
        car.draw(screen)
        
        # Custom Overlay (HUD)
        if on_frame:
            on_frame(None, car, None, "DRAW", screen)
        
        # UI
        font = pygame.font.SysFont(None, 24)
        status_color = RED if car.collision else BLACK
        txt = font.render(f"Sensors: L:{sensors[0]:.2f} F:{sensors[1]:.2f} R:{sensors[2]:.2f}", True, status_color)
        screen.blit(txt, (30, 30))
        
        if is_rec:
            rec_txt = font.render("● RECORDING", True, RED)
            screen.blit(rec_txt, (WIDTH - 150, 30))
        
        if is_auto:
            auto_txt = font.render("● AUTO", True, BLUE)
            screen.blit(auto_txt, (WIDTH - 250, 30))
        
        help_txt = font.render("WASD: Drive | R: Rec | Z: Undo | S: Save | M: Auto", True, BLACK)
        screen.blit(help_txt, (30, 60))
        
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    run_simulation()
