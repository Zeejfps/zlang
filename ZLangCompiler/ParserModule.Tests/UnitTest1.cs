using LexerModule;

namespace ParserModule.Tests;

public class Tests
{
    [SetUp]
    public void Setup()
    {
    }

    [Test]
    public void Test1()
    {
        const string input = "var test: u32 = 10;";
        var tokens = Lexer.Tokenize(input);
        var ast = Parser.Parse(tokens);
        var printer = new AstPrinter();
        ast.Root.Accept(printer);
        var result = printer.ToString();
        Assert.Pass();
    }
}