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
        
        Assert.Pass();
    }
}