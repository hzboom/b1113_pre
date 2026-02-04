import java.awt.Rectangle;

public class Food {
    private int x; // X-coordinate of the food
    private int y; // Y-coordinate of the food

    /**
     * Constructor - Spawns the food at a random location when the game starts.
     */

    public Food() {
        this.random_spawn();
    }

    /**
     * Randomly spawns food on the grid, ensuring it does not appear on the snake's body.
     */

    public void random_spawn() {
        // Generate random X and Y coordinates within the game grid (0..width-1 / 0..height-1)
        x = (int) (Math.random() * Game.width);
        y = (int) (Math.random() * Game.height);
    }

    // Getters and Setters

    public int getX() {
        return x;
    }

    public void setX(int x) {
        this.x = x;
    }

    public int getY() {
        return y;
    }

    public void setY(int y) {
        this.y = y;
    }
}
