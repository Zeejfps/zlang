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
    public void Test1()
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
}