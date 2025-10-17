using LexerModule;
using ParserModule;

namespace CodeGenModule.Tests;

public class CodeGenTests
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
        var tokenReader = new TokenReader(tokens);
        var ast = Parser.ParseFunctionDefinition(tokenReader);
        
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
            module test {
                func add(x: u32, y: u32) -> u32 {
                    return x + y;
                }
                
                func main() {
                    add(2, 2);
                    return;
                }
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var compilationUnit = Parser.ParseModuleDefinition(tokenReader);
        
        var codeGenerator = new CodeGenerator();
        compilationUnit.Accept(codeGenerator);
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
        var tokenReader = new TokenReader(tokens);
        var ast = Parser.ParseFunctionDefinition(tokenReader);
        
        var codeGenerator = new CodeGenerator();
        ast.Accept(codeGenerator);
        codeGenerator.Verify();
        
        codeGenerator.SaveToFile("ifstmt.asm");
        
        Assert.Pass();
    }
    
    [Test]
    public void TestIfElseStatement()
    {
        const string input =
            """
            func test(x: u32, y: u32) -> u32 {
                if (x < y) {
                    return 10;
                } else {
                    return x + y;
                }
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var ast = Parser.ParseFunctionDefinition(tokenReader);
        
        var codeGenerator = new CodeGenerator();
        ast.Accept(codeGenerator);
        codeGenerator.Verify();
        
        codeGenerator.SaveToFile("ifelsestmt.asm");
        
        Assert.Pass();
    }
    
    [Test]
    public void TestExternFunctionDeclaration()
    {
        const string input =
            """
            extern func WriteConsoleA(
                hConsoleOutput: ptr, 
                lpBuffer: ptr<u16>, 
                nNumberOfCharsToWrite: u32,
                lpNumberOfCharsWritten: ptr<u32>,
                lpReserved: ptr
            ) -> i32;
            """;
        
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var ast = Parser.ParseExternFunctionDeclaration(tokenReader);
        
        var codeGenerator = new CodeGenerator();
        ast.Accept(codeGenerator);
        codeGenerator.Verify();
        
        codeGenerator.SaveToFile("externfunc.asm");
        
        Assert.Pass();
    }
    
    [Test]
    public void TestFunctionCallDeclaration()
    {
        const string input =
            """
            module main {
                
                func WriteConsoleA(
                    hConsoleOutput: u32, 
                    lpBuffer: u32, 
                    nNumberOfCharsToWrite: u32,
                    lpNumberOfCharsWritten: u32,
                    lpReserved: u32
                ) -> i32 {
                    return 0;
                }
                
                func main() {
                    WriteConsoleA(0, 0, 0, 0, 0);
                }
            }
            """;
        
        var tokens = Lexer.Tokenize(input);
        var tokenReader = new TokenReader(tokens);
        var moduleDefinition = Parser.ParseModuleDefinition(tokenReader);
        
        var codeGenerator = new CodeGenerator();
        moduleDefinition.Accept(codeGenerator);
        codeGenerator.Verify();
        
        codeGenerator.SaveToFile("externCall.asm");
        
        Assert.Pass();
    }
}