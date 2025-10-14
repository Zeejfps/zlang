using LexerModule;
using ParserModule;

namespace CodeGenModule.Tests;

public class Tests
{
    [SetUp]
    public void Setup()
    {
    }

    [Test]
    public void TestMainFunc()
    {
        const string input =
            """
            func main() {
                return;
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var ast = Parser.Parse(tokens);
        
        var codeGenerator = new CodeGenerator();
        ast.Accept(codeGenerator);
        codeGenerator.Verify();
        
        codeGenerator.SaveToFile("test.asm");
        
        Assert.Pass();
    }
    
    [Test]
    public void TestTwoFuncs()
    {
        const string input =
            """
            func main() {
                return;
            }
            
            func add(x: u32, y: u32) -> u32 {
                return x + y;
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var ast = Parser.Parse(tokens);
        
        var codeGenerator = new CodeGenerator();
        ast.Accept(codeGenerator);
        codeGenerator.Verify();
        
        codeGenerator.SaveToFile("test2.asm");
        
        Assert.Pass();
    }
    
    [Test]
    public void TestIfStatement()
    {
        const string input =
            """
            func test(x: u32, y: u32) -> u32 {
                if (x < y) {
                }
                return x + y;
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var ast = Parser.Parse(tokens);
        
        var codeGenerator = new CodeGenerator();
        ast.Accept(codeGenerator);
        codeGenerator.Verify();
        
        codeGenerator.SaveToFile("ifstmt.asm");
        
        Assert.Pass();
    }
    
    [Test]
    public void TestIfElseStatement()
    {
        // TODO: I need to distinguish between a pass by ref and value to properly return Z here
        const string input =
            """
            func test(x: u32, y: u32) -> u32 {
                if (x < y) {
                    return 10;
                } else {
                    var z = 13;
                    return z;
                }
                return x + y;
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var ast = Parser.Parse(tokens);
        
        var codeGenerator = new CodeGenerator();
        ast.Accept(codeGenerator);
        codeGenerator.Verify();
        
        codeGenerator.SaveToFile("ifelsestmt.asm");
        
        Assert.Pass();
    }
}